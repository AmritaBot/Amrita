"""Amrita资源模板模块

该模块定义了Amrita项目所需的各类资源模板，包括环境配置、git忽略文件、README模板等。
"""

# 默认环境配置文件内容
DOTENV = """ENVIRONMENT=dev
DRIVER=~fastapi
PORT=8080
HOST=127.0.0.1
LOCALSTORE_USE_CWD=true
DATABASE_URL=aiosqlite:///db.sqlite3
LOG_DIR=logs
BOT_NAME=Amrita
RATE_LIMIT=5
WEBUI_ENABLE=true
WEBUI_USER_NAME=admin
WEBUI_PASSWORD=admin123"""

# 开发环境配置文件内容
DOTENV_DEV = """LOG_LEVEL=DEBUG"""

# 生产环境配置文件内容
DOTENV_PROD = """"""

# Git忽略文件内容
GITIGNORE = """# Created by https://www.toptal.com/developers/gitignore/api/python
# Edit at https://www.toptal.com/developers/gitignore?templates=python

### Python ###
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
#  Usually these files are written by a python script from a template
#  before PyInstaller builds the exe, so as to inject date/other infos into it.
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
#   For a library or package, you might want to ignore these files since the code is
#   intended to run in multiple environments; otherwise, check them in:
# .python-version

# pipenv
#   According to pypa/pipenv#598, it is recommended to include Pipfile.lock in version control.
#   However, in case of collaboration, if having platform-specific dependencies or dependencies
#   having no cross-platform support, pipenv may install dependencies that don't work, or not
#   install all needed dependencies.
#Pipfile.lock

# poetry
#   Similar to Pipfile.lock, it is generally recommended to include poetry.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#   https://python-poetry.org/docs/basic-usage/#commit-your-poetrylock-file-to-version-control
#poetry.lock

# pdm
#   Similar to Pipfile.lock, it is generally recommended to include pdm.lock in version control.
#pdm.lock
#   pdm stores project-wide configurations in .pdm.toml, but it is recommended to not include it
#   in version control.
#   https://pdm.fming.dev/#use-with-ide
.pdm.toml

# PEP 582; used by e.g. github.com/David-OConnor/pyflow and github.com/pdm-project/pdm
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
#  JetBrains specific template is maintained in a separate JetBrains.gitignore that can
#  be found at https://github.com/github/gitignore/blob/main/Global/JetBrains.gitignore
#  and can be added to the global gitignore or merged into this file.  For a more nuclear
#  option (not recommended) you can uncomment the following to ignore the entire idea folder.
#.idea/

### Python Patch ###
# Poetry local configuration file - https://python-poetry.org/docs/configuration/#local-configuration
poetry.toml

# ruff
.ruff_cache/

# LSP config files
pyrightconfig.json

# End of https://www.toptal.com/developers/gitignore/api/python"""

# README文件模板
README = """
# {project_name}

## How to start

1. generate project using `amrita init` .
2. create your plugin using `nb plugin create` .
3. writing your plugins under `{project_name}/plugins` folder.
4. run your bot using `amrita run --reload` .

## Documentation

[AmritaDocs](https://amrita.suggar.top)

See Nonebot [Docs](https://nonebot.dev/)
"""

# 插件示例代码模板
EXAMPLE_PLUGIN = """from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent

# Register your commands here
{name} = on_command("{name}")

@{name}.handle()
async def handle_function(event: MessageEvent):
    await {name}.finish("Hello from {name}!")
"""

# 插件配置文件模板
EXAMPLE_PLUGIN_CONFIG = """# Configuration for {name} plugin
from pydantic import BaseModel
from nonebot import get_plugin_config
class Config(BaseModel):
    ...
    # Add your configuration here

# Get your config by using `get_plugin_config(Config)`
"""
