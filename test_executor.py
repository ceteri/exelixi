#!/usr/bin/env python


import sys
import threading
import time

import mesos
import mesos_pb2


class TestExecutor (mesos.Executor):
    def launchTask (self, driver, task):

        # create a thread to run the task: tasks should always be run
        # in new threads or processes, rather than inside launchTask
        def run_task():
            print "requested task %s" % task.task_id.value

            update = mesos_pb2.TaskStatus()
            update.task_id.value = task.task_id.value
            update.state = mesos_pb2.TASK_RUNNING
            update.data = "running %s" % task.task_id.value
            driver.sendStatusUpdate(update)
            print "sent status update 1..."

            ## NB: this is where one would perform the requested task
            print "perform task %s" % task.task_id.value

            update = mesos_pb2.TaskStatus()
            update.task_id.value = task.task_id.value
            update.state = mesos_pb2.TASK_FINISHED
            update.data = "completed %s" % task.task_id.value
            driver.sendStatusUpdate(update)
            print "sent status update 2..."


        # now run the requested task
        thread = threading.Thread(target=run_task)
        thread.start()


    def frameworkMessage (self, driver, message):
        # send the message back to the scheduler
        driver.sendFrameworkMessage(message)


if __name__=='__main__':
    print "Starting executor..."

    driver = mesos.MesosExecutorDriver(TestExecutor())
    sys.exit(0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1)
