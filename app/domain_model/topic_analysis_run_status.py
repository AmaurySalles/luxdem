from enum import Enum


class TopicAnalysisRunStatus(str, Enum):
    Pending = "pending"
    Running = "running"
    Done = "done"
    Failed = "failed"
