import asyncio
import json
from pathlib import Path
from typing import Optional

from abq import BQ

from bqflow._helper import convert_size, mkdir_if_not_exists


class Client:
    def __init__(self, project_id: Optional[str]):
        self.bq = BQ(project_id=project_id)

    def execute_query(self, sql_path: Path, output: Optional[Path] = None, nowait: bool = False):
        with open(sql_path, "r") as f:
            sql = f.read()

        async def query():
            byte = await self.bq.dry_query(sql=sql)
            print("Processed:", convert_size(int(byte)))
            job = await self.bq.query(sql=sql)
            if not nowait:
                await job.wait()
            return job

        job = asyncio.run(query())

        if output is not None:
            result = asyncio.run(job.result())

            mkdir_if_not_exists(output)
            with open(output, "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            from pprint import pprint

            pprint(result)
