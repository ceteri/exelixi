#!/usr/bin/env python


import json
import os
import sys
import time
import urllib2

import mesos
import mesos_pb2

TOTAL_TASKS = 5
TASK_CPUS = 1
TASK_MEM = 32


class TestScheduler (mesos.Scheduler):
    def __init__ (self, executor):
        self.executor = executor
        self.taskData = {}
        self.tasksLaunched = 0
        self.tasksFinished = 0
        self.messagesSent = 0
        self.messagesReceived = 0


    def registered (self, driver, frameworkId, masterInfo):
        print "registered with framework ID %s" % frameworkId.value


    def resourceOffers (self, driver, offers):
        print "got %d resource offers" % len(offers)

        for offer in offers:
            tasks = []
            print "got resource offer %s" % offer.id.value

            if self.tasksLaunched < TOTAL_TASKS:
                tid = self.tasksLaunched
                self.tasksLaunched += 1

                print "accepting offer on %s to start task %d" % (offer.hostname, tid)

                task = mesos_pb2.TaskInfo()
                task.task_id.value = str(tid)
                task.slave_id.value = offer.slave_id.value
                task.name = "task %d" % tid
                task.executor.MergeFrom(self.executor)

                cpus = task.resources.add()
                cpus.name = "cpus"
                cpus.type = mesos_pb2.Value.SCALAR
                cpus.scalar.value = TASK_CPUS

                mem = task.resources.add()
                mem.name = "mem"
                mem.type = mesos_pb2.Value.SCALAR
                mem.scalar.value = TASK_MEM

                tasks.append(task)
                self.taskData[task.task_id.value] = (offer.slave_id, task.executor.executor_id)                  

            driver.launchTasks(offer.id, tasks)


    def statusUpdate (self, driver, update):
        print "task %s is in state %d" % (update.task_id.value, update.state)
        print "actual:", repr(str(update.data))

        if update.state == mesos_pb2.TASK_FINISHED:
            self.tasksFinished += 1

            if self.tasksFinished == TOTAL_TASKS:
                print "all tasks done, waiting for final framework message"

            slave_id, executor_id = self.taskData[update.task_id.value]

            self.messagesSent += 1
            driver.sendFrameworkMessage(executor_id, slave_id, 'data with a \0 byte')


    def frameworkMessage (self, driver, executorId, slaveId, message):
        self.messagesReceived += 1
        print "received message:", repr(str(message))

        if self.messagesReceived == TOTAL_TASKS:
            if self.messagesReceived != self.messagesSent:
                print "sent", self.messagesSent, "but received", self.messagesReceived
                sys.exit(1)

            print "all tasks done, and all messages received; exiting"
            driver.stop()


if __name__=='__main__':
    if len(sys.argv) != 2:
        print "Usage:\n  %s <leader master host:port>" % sys.argv[0]
        sys.exit(1)

    # determine the leader among the Mesos masters
    response = urllib2.urlopen("http://" + sys.argv[1] + "/master/state.json")
    data = json.loads(response.read())
    master_uri = data["leader"].split("@")[1]
    print master_uri

    # initialize an executor
    executor = mesos_pb2.ExecutorInfo()
    executor.executor_id.value = "default"
    executor.command.value = os.path.abspath("/home/ubuntu/exelixi/test_executor.py")
    executor.name = "Test Executor (Python)"
    executor.source = "python_test"

    framework = mesos_pb2.FrameworkInfo()
    framework.user = "" # Have Mesos fill in the current user.
    framework.name = "Test Framework (Python)"

    # TODO(vinod): make checkpointing the default when it is default
    # on the slave

    if os.getenv("MESOS_CHECKPOINT"):
        print "enabling checkpoint for the framework"
        framework.checkpoint = True

    if os.getenv("MESOS_AUTHENTICATE"):
        print "enabling authentication for the framework"

        if not os.getenv("DEFAULT_PRINCIPAL"):
            print "expecting authentication principal in the environment"
            sys.exit(1);

        if not os.getenv("DEFAULT_SECRET"):
            print "expecting authentication secret in the environment"
            sys.exit(1);

        credential = mesos_pb2.Credential()
        credential.principal = os.getenv("DEFAULT_PRINCIPAL")
        credential.secret = os.getenv("DEFAULT_SECRET")

        driver = mesos.MesosSchedulerDriver(TestScheduler(executor), framework, master_uri, credential)
    else:
        driver = mesos.MesosSchedulerDriver(TestScheduler(executor), framework, master_uri)

    # ensure that the driver process terminates
    status = 0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1
    driver.stop();
    sys.exit(status)
