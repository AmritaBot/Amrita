from pathlib import Path

from amrita.plugins.chat.utils.models import InsightsModel
from amrita.plugins.webui.API import (
    PageContext,
    PageResponse,
    SideBarCategory,
    SideBarManager,
    TemplatesManager,
    on_page,
)

TemplatesManager().add_templates_dir(Path(__file__).resolve().parent / "templates")

SideBarManager().add_sidebar_category(
    SideBarCategory(name="聊天管理", icon="fa fa-comments", url="#")
)


@on_page("/manage/chat/function", page_name="信息统计", category="聊天管理")
async def _(ctx: PageContext):
    insight = await InsightsModel.get()
    return PageResponse(
        name="function.html",
        context={
            "token_prompt": insight.token_input,
            "token_completion": insight.token_output,
            "usage_count": insight.usage_count,
        },
    )
