class JobCancelled(Exception):
    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
        super().__init__(f"Job {job_id} cancelled")
