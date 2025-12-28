from pathlib import Path
from typing import Any

from nonebot import logger

from amrita.plugins.chat.config import config_manager
from amrita.plugins.chat.utils.models import InsightsModel
from amrita.plugins.webui.API import (
    JSONResponse,
    PageContext,
    PageResponse,
    Request,
    SideBarCategory,
    SideBarManager,
    TemplatesManager,
    on_page,
)

# 导入API路由
from amrita.plugins.webui.API import app as router

TemplatesManager().add_templates_dir(Path(__file__).resolve().parent / "templates")

SideBarManager().add_sidebar_category(
    SideBarCategory(name="聊天管理", icon="fa fa-comments", url="#")
)

KEY_PLACEHOLDER = "••••••••"


@router.post("/api/chat/models")
async def create_model(request: Request):
    try:
        data: dict[str, Any] = await request.json()
        name = data.get("name")
        model = data.get("model", "")
        base_url = data.get("base_url", "")
        api_key = data.get("api_key", "")
        protocol = data.get("protocol", "__main__")
        multimodal = data.get("multimodal", False)
        thought_chain_model = data.get("thought_chain_model", False)

        if not name:
            return JSONResponse(
                {"success": False, "message": "缺少模型预设名称"}, status_code=400
            )

        # 创建模型预设
        from amrita.plugins.chat.config import ModelPreset

        preset = ModelPreset(
            name=name,
            model=model,
            base_url=base_url,
            api_key=api_key,
            protocol=protocol,
            multimodal=multimodal,
            thought_chain_model=thought_chain_model,
        )

        # 保存模型预设到文件
        preset_path = config_manager.custom_models_dir / f"{name}.json"
        preset.save(preset_path)

        # 重新加载模型列表
        await config_manager.get_all_presets(cache=False)

        return JSONResponse(
            {"success": True, "message": f"模型预设 {name} 创建成功"}, status_code=200
        )
    except Exception as e:
        logger.opt(exception=e, colors=True).error("创建模型预设失败")
        return JSONResponse(
            {"success": False, "message": f"创建模型预设失败: {e!s}"},
            status_code=500,
        )


@router.put("/api/chat/models/{name}")
async def update_model(request: Request, name: str):
    try:
        # 获取现有的模型预设
        preset = await config_manager.get_preset(name, fix=False, cache=False)

        if not preset:
            return JSONResponse(
                {"success": False, "message": f"模型预设 {name} 不存在"},
                status_code=404,
            )

        data: dict[str, Any] = await request.json()

        # 更新字段
        for key, value in data.items():
            if hasattr(preset, key):
                setattr(preset, key, value)

        # 保存模型预设到文件
        preset_path = config_manager._model_name2file[name]

        preset.save(preset_path)

        # 重新加载模型列表
        await config_manager.get_all_presets(cache=False)

        return JSONResponse(
            {"success": True, "message": f"模型预设 {name} 更新成功"}, status_code=200
        )
    except Exception as e:
        logger.opt(exception=e, colors=True).error("[webui] 模型预设更新失败: %s", e)
        return JSONResponse(
            {"success": False, "message": f"更新模型预设失败: {e!s}"},
            status_code=500,
        )


@router.delete("/api/chat/models/{name}")
async def delete_model(name: str):
    try:
        preset_path = config_manager._model_name2file[name]

        if not preset_path.exists():
            return JSONResponse(
                {"success": False, "message": f"模型预设 {name} 不存在"},
                status_code=404,
            )

        # 删除文件
        preset_path.unlink()

        # 重新加载模型列表
        await config_manager.get_all_presets(cache=False)
        del config_manager._model_name2file[name]

        return JSONResponse(
            {"success": True, "message": f"模型预设 {name} 删除成功"}, status_code=200
        )
    except Exception as e:
        logger.opt(exception=e, colors=True).error(f"Error in delete preset {name}")
        return JSONResponse(
            {"success": False, "message": f"删除模型预设失败: {e!s}"},
            status_code=500,
        )


@router.get("/api/chat/models")
async def get_models():
    try:
        models = await config_manager.get_all_presets(cache=False)
        model_data = [
            {
                "name": model.name,
                "model": model.model,
                "base_url": model.base_url,
                "api_key": KEY_PLACEHOLDER,
                "protocol": model.protocol,
                "multimodal": model.multimodal,
                "thought_chain_model": model.thought_chain_model,
            }
            for model in models
        ]

        return JSONResponse({"success": True, "models": model_data}, status_code=200)
    except Exception as e:
        logger.opt(exception=e, colors=True).error("获取模型预设列表失败")
        return JSONResponse(
            {"success": False, "message": f"获取模型预设列表失败: {e!s}"},
            status_code=500,
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


@on_page("/manage/chat/models", page_name="模型预设", category="聊天管理")
async def _(ctx: PageContext):
    models = await config_manager.get_all_presets(cache=False)
    current_default = config_manager.config.preset

    model_data = [
        {
            "name": model.name,
            "model": model.model,
            "base_url": model.base_url,
            "api_key": KEY_PLACEHOLDER,
            "protocol": model.protocol,
            "multimodal": model.multimodal,
            "thought_chain_model": model.thought_chain_model,
        }
        for model in models
    ]

    return PageResponse(
        name="models.html",
        context={
            "models": model_data,
            "current_default": current_default,
            "key_placeholder": KEY_PLACEHOLDER,
        },
    )
