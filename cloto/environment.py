__author__ = 'Geon'
import sys
import pika
import sqlite3 as db
import logging
import clips
import json
import requests
from configuration import LOGGING_PATH, RABBITMQ_URL, CLIPS_PATH
logger = logging.getLogger('environments')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOGGING_PATH + '/%s.log' % sys.argv[1])
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


def main():
    tenantId = sys.argv[1]

    def env_id():
        return clips.Symbol(sys.argv[1])

    # the following dictionary will contain the environment specific functions
    ENV_SPECIFIC_FUNCTIONS = {}

    # ...and this wrapper calls in turn the functions associated with certain
    #  names for each environment
    def envCallSpecificFunction(e_id, funcname, *args):
        f = ENV_SPECIFIC_FUNCTIONS[e_id][funcname]
        return f(*args)
    clips.RegisterPythonFunction(envCallSpecificFunction, 'env-call-specific-func')

    # now we need some helpers to make it easier to set up the environment and
    #  the map of environment specific functions
    def PrepareEnvironment(e):
        eid = env_id()
        ENV_SPECIFIC_FUNCTIONS[eid] = {}   # a map of functions
        e.Identifier = eid                  # so that we can always get it back
        return eid

    def GetNotificationUrl(ruleName, serverId):
        conn = db.connect("cloto.db")
        conn.row_factory = db.Row
        cur = conn.cursor()
        SQL = "SELECT url from cloto_subscription S join cloto_specificrule R on S.ruleId=R.specificRule_Id " \
              "WHERE name='%s' AND S.serverId='%s';" \
              % (ruleName, serverId)
        cur.execute(SQL)
        while True:
            r = cur.fetchone()
            if not r:
                conn.close()
                break
            else:
                url = r['url']
        return url

    def NotifyEmail(email, serverId, description, url):
        print("[+] Test %s" % email)
        #headers ={'X-Auth-Token':'test'}
        data = json.dumps({'action': 'notifyEmail', 'email': '%s', 'description': '%s'} % (email, description))
        r = requests.get(url)
        if r.status_code == 200:
            logger.info("[+] mail sent to %s about server %s.--- Response: %d" % (email, serverId, url, r.status_code))
        else:
            logger.info("[+] ERROR Sending mail to %sabout server %s.--- %s Response: %d"
                        % (email, serverId, url, r.status_code))

    def NotifyScaleUp(serverId, url):
        #headers ={'X-Auth-Token':'test'}
        data = json.dumps({'action': 'scaleUp', 'serverId': '%s'} % serverId)
        r = requests.get(url)
        if r.status_code == 200:
            logger.info("[+] ScaleUp message sent to %s about server %s.--- Response: %d"
                        % (url, serverId, r.status_code))
        else:
            logger.error("[+] ScaleUp message sent to %s about server %s.--- Response: %d"
                         % (url, serverId, r.status_code))

    def NotifyScaleDown(serverId, url):
        #headers ={'X-Auth-Token':'test'}
        data = json.dumps({'action': 'scaleDown', 'serverId': '%s'} % serverId)
        r = requests.get(url)
        if r.status_code == 200:
            logger.info("[+] ScaleDown message sent to %s about server %s.--- Response: %d"
                        % (url, serverId, r.status_code))
        else:
            logger.error("[+] ScaleDown message sent to %s about server %s.--- Response: %d"
                         % (url, serverId, r.status_code))

    def AddSpecificFunction(e, func, funcname=None):
        try:
            eid = e.Identifier
        except:
            raise ValueError("The Environment has not been prepared")
        if funcname is None:
            funcname = func.__name__    # if needed
        ENV_SPECIFIC_FUNCTIONS[eid][funcname] = func
        num_args = func.func_code.co_argcount
        seq_args = " ".join(['?a%s' % x for x in range(num_args)])
        e.BuildFunction(
            funcname,
            seq_args,
            "(return (python-call env-call-specific-func %s %s %s))" % (
                eid, funcname, seq_args))

    def get_rules_from_db(tenantId):
        import sqlite3 as db
        conn = db.connect("cloto.db")
        conn.row_factory = db.Row
        cur = conn.cursor()
        SQL = "SELECT * FROM cloto_specificrule WHERE specificRule_Id IN " \
              "(SELECT ruleId FROM cloto_subscription WHERE serverId IN " \
              "(SELECT serverId FROM cloto_entity WHERE tenantId='%s'))" % tenantId
        cur.execute(SQL)
        while True:
            r = cur.fetchone()
            if not r:
                print("not r")
                conn.close()
                break
            else:
                rule_name = r['name']
                rule_cond = r['condition']
                rule_action = r['action']
                e1.BuildRule(rule_name, rule_cond, rule_action)

    e1 = clips.Environment()
    PrepareEnvironment(e1)
    clips.RegisterPythonFunction(NotifyEmail, "notify-email")
    clips.RegisterPythonFunction(NotifyScaleUp, "notify-scale-up")
    clips.RegisterPythonFunction(NotifyScaleDown, "notify-scale-down")
    clips.RegisterPythonFunction(GetNotificationUrl, "get-notification-url")
    e1.Load("%s/model.clp" % CLIPS_PATH)

    while (True):
        try:

            connection = pika.BlockingConnection(pika.ConnectionParameters(
                    host=RABBITMQ_URL))
            channel = connection.channel()

            channel.exchange_declare(exchange="update_" + tenantId,
                                     type='fanout')

            result = channel.queue_declare(exclusive=True)
            queue_name = result.method.queue

            channel.queue_bind(exchange="update_" + tenantId,
                               queue=queue_name)

            logger.info(' [*] Environment started. Waiting for Facts')

            def callback(ch, method, properties, body):
                decoded = json.loads(body)
                template = e1.FindTemplate("serverFact")
                server_fact = e1.Fact(template)
                server_fact.Slots['server-id'] = decoded['serverId']
                server_fact.Slots['cpu'] = int(decoded['cpu'])
                server_fact.Assert()
                logger.info(" [x] received fact: %s" % body)
                get_rules_from_db(tenantId)
                e1.Run()

            channel.basic_consume(callback,
                                  queue=queue_name,
                                  no_ack=True)

            channel.start_consuming()
        except db.Error, e:
            logger.error("Error %s:" % e.args[0])
        except Exception as ex:
            if ex.message:
                logger.error("Error: %s" % ex.message)
        finally:
            connection.close()

if __name__ == '__main__':
    main()
