#!/usr/bin/env python


import sys
import threading
import time

import mesos
import mesos_pb2


class MesosExecutor (mesos.Executor):
    # https://github.com/apache/mesos/blob/master/src/python/src/mesos.py

    def launchTask (self, driver, task):
        """
        Invoked when a task has been launched on this executor
        (initiated via Scheduler.launchTasks).  Note that this task
        can be realized with a thread, a process, or some simple
        computation, however, no other callbacks will be invoked on
        this executor until this callback has returned.
        """

        # create a thread to run the task: tasks should always be run
        # in new threads or processes, rather than inside launchTask
        def run_task():
            print "requested task %s" % task.task_id.value

            update = mesos_pb2.TaskStatus()
            update.task_id.value = task.task_id.value
            update.state = mesos_pb2.TASK_RUNNING
            update.data = 'running: data with a \0 byte'
            driver.sendStatusUpdate(update)
            print "sent status update 1..."

            ## NB: this is where one would perform the requested task
            print "perform task %s" % task.task_id.value

            update = mesos_pb2.TaskStatus()
            update.task_id.value = task.task_id.value
            update.state = mesos_pb2.TASK_FINISHED
            update.data = 'complete: data with a \0 byte'
            driver.sendStatusUpdate(update)
            print "sent status update 2..."

        # now run the requested task
        thread = threading.Thread(target=run_task)
        thread.start()


    def frameworkMessage (self, driver, message):
        """
        Invoked when a framework message has arrived for this
        executor. These messages are best effort; do not expect a
        framework message to be retransmitted in any reliable fashion.
        """

        # send the message back to the scheduler
        driver.sendFrameworkMessage(message)


if __name__=='__main__':
    print "Starting executor..."

    driver = mesos.MesosExecutorDriver(MesosExecutor())
    sys.exit(0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1)
