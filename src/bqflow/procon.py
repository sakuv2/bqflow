import asyncio
from asyncio import Queue

from abq import BQ
from abq.bq import JobResult

from bqflow._helper import ifnull
from bqflow.fields import Workflow
from bqflow.parameter import parse_param
from bqflow.report import TaskReport
from bqflow.task import Query
from bqflow.tracer import TreeTracer


class Producer:
    def __init__(self, tt: TreeTracer, queue: Queue[Query]):
        self.tt = tt
        self.added_tasks: list[list[str]] = []
        self.q = queue

    def is_done(self):
        root = self.tt.statuses.get_root_task()
        return root.done

    async def task_loop(self) -> bool:
        while not self.is_done():
            await self._add_task()
            await asyncio.sleep(0.1)
        return True

    async def _add_task(self):
        tasks = [t for t in self.tt.get_tasks() if t.name not in self.added_tasks]
        for task in tasks:
            self.added_tasks.append(task.name)
            self.q.put_nowait(task)


class Consumer:
    def __init__(self, tt: TreeTracer, project_name: str, queue: Queue[Query]):
        self.tt = tt
        self.bq = BQ(project_id=project_name)
        self.q = queue
        self.done = False
        self.reports: list[TaskReport] = []

    def stop(self):
        self.done = True

    async def make_worker(self, worker: int):
        await asyncio.gather(*[self.execute(i + 1) for i in range(worker)])

    async def execute(self, i):
        while not self.done:
            if not self.q.empty():
                task = self.q.get_nowait()
                params = [parse_param(param) for param in task.parameters]
                job: JobResult = await self.bq.query(sql=task.sql, parameters=params)
                await job.wait()

                duration = job.info.statistics.endTime - job.info.statistics.startTime
                total_bytes_billed = ifnull(job.info.statistics.query.totalBytesBilled, 0)
                tr = TaskReport(
                    name=task.name,
                    duration=duration / 1000,
                    total_bytes_billed=total_bytes_billed,
                )
                self.reports.append(tr)

                self.tt.task_done(task.name)
            await asyncio.sleep(0.1)


class ProCon:
    def __init__(self, wf: Workflow, project_name: str, max_size=10):
        self.q: list[Query] = Queue()
        self.tt = TreeTracer(wf)
        self.tt.task_update()
        self.producer = Producer(self.tt, self.q)
        self.consumer = Consumer(self.tt, project_name, self.q)
        self.max_size = max_size

    def run(self) -> list[TaskReport]:
        return asyncio.run(self.execute())

    async def execute(self) -> list[TaskReport]:
        producer = asyncio.create_task(self.producer.task_loop())
        consumer = asyncio.create_task(self.consumer.make_worker(self.max_size))

        await producer
        self.consumer.stop()
        await consumer
        return self.consumer.reports
