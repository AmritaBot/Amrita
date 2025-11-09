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
    insight_all = await InsightsModel.get_all()
    return PageResponse(
        name="function.html",
        context={
            "token_prompt": insight.token_input,
            "token_completion": insight.token_output,
            "usage_count": insight.usage_count,
            "chart_data": [
                {
                    "date": i.date,
                    "token_input": i.token_input,
                    "token_output": i.token_output,
                    "usage_count": i.usage_count,
                }
                for i in insight_all
            ],
        },
    )
