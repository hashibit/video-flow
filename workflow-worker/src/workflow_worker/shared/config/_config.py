from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="IDRS_ENGINE_CONF",
    settings_files=[
        "engine/configs/global.yaml",
        "engine/configs/service/auc.yaml",
        "engine/configs/service/human_detection.yaml",
        "engine/configs/service/face_verification.yaml",
        "engine/configs/service/general_ocr.yaml",
        "engine/configs/service/person_tracking.yaml",
        "engine/configs/service/document_ocr.yaml",
        "engine/configs/service/idcard_ocr.yaml",
        "engine/configs/service/handwriting_ocr.yaml",
    ],
    env_switcher="IDRS_ENGINE_ENV",
    environments=True,
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load this files in the order.

# two ways for switching to prod env:
# 1. add `env` argument in Dynaconf class, eg. `Dynaconf(env='production', ...)`
# 2. run `export ENV_FOR_DYNACONF=production`
