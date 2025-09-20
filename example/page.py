from pathlib import Path

from amrita.plugins.webui.API import (
    PageContext,
    PageResponse,
    TemplatesManager,
    on_page,
)

# 添加模板目录
TemplatesManager().add_templates_dir(Path(__file__).resolve().parent / "templates_example")

# 创建页面
@on_page(path="/path/to/your/page", page_name="我的Amrita 页面", category="其他功能")
async def _(ctx: PageContext):
    return PageResponse(name="my_page.html.jinja2", context={"title": "我的Amrita 页面"})
