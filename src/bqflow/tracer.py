from __future__ import annotations

from typing import Optional, TypeVar

from pydantic import BaseModel

from bqflow.fields import DAGTask, Parameter, Template, Workflow
from bqflow.task import Query


class Status(BaseModel):
    template_name: str
    task_names: list[str]
    done_task_names: list[str]
    required_task_names: list[str]
    parameters: list[Parameter] = []
    done: bool = False

    def contain_recursive(self):
        return len(self.template_names) != len(set(self.template_names))


class Statuses(BaseModel):
    statuses: list[Status] = []

    def __getitem__(self, i):
        return self.statuses[i]

    def __iter__(self) -> Status:
        return iter(self.statuses)

    def __len__(self):
        return len(self.statuses)

    def append(self, status: Status):
        tasks_names = [s.task_names for s in self.statuses]
        if status.task_names in tasks_names:
            raise ValueError(f"{status.task_names}はすでに追加されています")
        self.statuses.append(status)

    def get_root_task(self):
        return self.find([])

    def find(self, task_names: list[str]) -> Status:
        result = [status for status in self.statuses if status.task_names == task_names]
        if result == []:
            raise KeyError(f"{task_names}は登録されているstatusesの中に存在しませんでした")
        return result[0]

    def parent(self, task_names: list[str]) -> Optional[Status]:
        return self.find(task_names[:-1]) if task_names != [] else None

    def done(self, task_names: list[str]):
        """指定したタスクを完了にする

        Args:
            task_names (list[str]): タスク名
        """
        status = self.find(task_names)

        # これ自身をdoneにする
        status.done = True

        # これの子供のstatusが全て完了しているか確認する
        flags = [s.done for s in self.statuses if s.task_names[:-1] == status.task_names]
        if not all(flags):
            raise RuntimeError(f"{task_names}の子供に完了していないtaskが存在します")

        # 必要タスクが全て終わっているか確認する
        sub = set(status.required_task_names) - set(status.done_task_names)
        if sub != set():
            raise RuntimeError(f"{sub}のタスクがまだ完了していません")

        # 親のdone_task_namesにこれの完了を登録する
        if task_names == []:
            return
        parent = self.find(task_names[:-1])
        parent.done_task_names.append(task_names[-1])

        # 親の全タスクが完了したか調べ、完了していたら親も完了にする
        sub = set(parent.required_task_names) - set(parent.done_task_names)
        if sub == set():
            self.done(parent.task_names)

    def executable_statuses(self) -> list[Status]:
        """実行可能なstatusを見つける

        Returns:
            list[Status]: 実行可能なstatus
        """
        executables = [s for s in self.statuses if not s.done and s.required_task_names == []]
        return executables


T = TypeVar("T")


def list_sub(xs: list[T], ys: list[T]) -> list[T]:
    """xsとysを比較して一致しなくなったところから後ろを返す

    Examples:
        list_sub([1, 2, 3], [1, 1]) >>> [2, 3]
        list_sub([1, 2, 3], [1, 2]) >>> [3]

    Args:
        xs (list[T]): リストlen(xs)>=len(ys)
        ys (list[T]): リスト

    Returns:
        list[T]: 差分
    """
    xs, ys = (xs, ys) if len(xs) >= len(ys) else (ys, xs)
    index = None
    if len(xs) == len(ys):
        return []
    for i in range(len(ys)):
        if xs[i] != ys[i]:
            index = i
            break
    else:
        index = len(ys)
    return xs[index : len(xs)]


def update_parameters(base: list[Parameter], update: list[Parameter]) -> list[Parameter]:
    base = {x.name: x for x in base}
    update = {x.name: x for x in update}
    base.update(update)
    return [x for x in base.values()]


def input_overwrite(inputs: list[Parameter], writes: list[Parameter]) -> list[Parameter]:
    inputs = {x.name: x for x in inputs}
    writes = {x.name: x for x in writes if x.name in list(inputs.keys())}
    sub = set(inputs.keys()) - set(writes.keys())
    if sub != set():
        raise ValueError(f"{sub}のパラメータが初期化できていません. yamlを確認してください")
    inputs.update(writes)
    return [x for x in inputs.values()]


class TreeTracer:
    def __init__(self, wf: Workflow):
        self.wf = wf
        # rootタスクを追加
        self.statuses: Statuses = Statuses(
            statuses=[
                Status(
                    template_name=wf.entrypoint,
                    task_names=[],
                    done_task_names=[],
                    required_task_names=self.required_tasks[wf.entrypoint],
                    parameters=wf.arguments.parameters,
                )
            ]
        )
        self.tasks = []
        self.task_update()

    @property
    def required_tasks(self) -> dict[str, list[str]]:
        dic: dict[str, list[str]] = {}
        for t in self.wf.templates:
            if t.type == "dag":
                dic[t.name] = [task.name for task in t.dag.tasks]
            elif t.type == "steps":
                dic[t.name] = sum([[s.name for s in ss] for ss in t.steps], [])
            else:
                dic[t.name] = []
        return dic

    @property
    def dags(self) -> list[tuple[str, DAGTask]]:
        """stepsとdagを全てdagに変換する

        Returns:
            list[tuple[str, DAGTask]]: [(テンプレート名, その中のDAGTask)]
        """
        return sum([self._convert_dag(template) for template in self.wf.templates], [])

    @property
    def queries(self) -> dict[str, Template]:
        return {temp.name: temp for temp in self.wf.templates if temp.type in ["run", "script"]}

    def get_tasks(self) -> list[Query]:
        statuese = self.statuses.executable_statuses()

        tasks: list[Query] = []
        for status in statuese:
            status.task_names

            temp = self.queries[status.template_name]
            params = input_overwrite(temp.inputs.parameters, status.parameters)

            if temp.run is None:
                with open(temp.script, "r") as f:
                    sql = f.read()
            else:
                sql = temp.run

            tasks.append(Query(name=status.task_names, sql=sql, parameters=params))
        return tasks

    def task_done(self, task_names: list[str]):
        """指定したタスクを完了にする

        Args:
            task_names (list[str]): 完了にしたいタスク名
        """
        self.statuses.done(task_names=task_names)
        self.task_update()

    def task_update(self):
        """タスクの完了を反映し実行可能タスクを追加する"""
        before_len = len(self.statuses)
        self._task_update_helper()
        while before_len != len(self.statuses):
            self._task_update_helper()
            before_len = len(self.statuses)

    def _task_update_helper(self):
        """一段階タスクを掘る"""
        statuses = [status for status in self.statuses if not status.done]
        tasks_names = [status.task_names for status in self.statuses]
        root_param = self.wf.arguments.parameters

        for status in statuses:
            template_name = status.template_name
            task_names = status.task_names
            dones = status.done_task_names
            for name, task in self.dags:
                # すでに追加されているタスクは無視
                if task_names + [task.name] in tasks_names:
                    continue
                #
                if name != template_name or task.name in dones:
                    continue
                # 依存タスクが全て完了しているタスクを列挙
                if len(set(task.dependencies) - set(dones)) == 0:
                    param = update_parameters(root_param, task.arguments.parameters)
                    self.statuses.append(
                        Status(
                            template_name=task.template,
                            task_names=task_names + [task.name],
                            done_task_names=[],
                            required_task_names=self.required_tasks[task.template],
                            parameters=param,
                        )
                    )

    @staticmethod
    def _convert_dag(template: Template) -> tuple[str, DAGTask]:
        dags = []
        if template.type == "steps":
            deps = []
            for steps in template.steps:
                step_deps = []
                for step in steps:
                    task = DAGTask(
                        name=step.name,
                        template=step.template,
                        dependencies=deps,
                        arguments=step.arguments,
                    )
                    step_deps.append(step.name)
                    dags.append((template.name, task))
                deps = step_deps
        elif template.type == "dag":
            for task in template.dag.tasks:
                dags.append((template.name, task))
        return dags
