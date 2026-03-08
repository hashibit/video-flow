
from pydantic import BaseModel

from workflow_worker.domain.entities.service.auc import AUCServiceResult


class SingleBannedWordDetectionJobCfg(BaseModel):
    """Banned Word Detection Job Config for single rule

    Attributes:
        id (int): rule point id
        banned_words (list[str]): list of banned words
        require_words (list[str]): list of required words
    """

    id: int
    banned_words: list[str]
    require_words: list[str]


class BannedWordDetectionJobCfg(BaseModel):
    """Banned Word Detection Job Config

    Attributes:
        id (int): job id
        auc_service_result (AUCServiceResult): AUC Service's result
        configs (list[SingleBannedWordDetectionJobCfg]): banned word detection job configs
    """

    id: int
    auc_service_result: AUCServiceResult | None
    configs: list[SingleBannedWordDetectionJobCfg]
