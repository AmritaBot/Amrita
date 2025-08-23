from .models import PluginData


def generate_menu(plugins: list[PluginData]) -> list[str]:
    head = "这是菜单列表，包含所有可用的功能和用法。\n"
    head += "模块列表\n"
    for plugin in plugins:
        if not plugin.metadata or not plugin.matcher_grouping:
            continue
        plugin_name = plugin.metadata.name
        head += f"\n{plugin_name}"

    menu_datas: list[str] = [head.strip()]
    for plugin in plugins:
        if not plugin.matcher_grouping or not plugin.metadata:
            continue

        plugin_title = f"{plugin.metadata.name}\n"
        plugin_markdown = plugin_title
        for matchers in plugin.matcher_grouping.values():
            for matcher_data in matchers:
                plugin_markdown += f" {matcher_data.name}: {matcher_data.description}"
                if matcher_data.usage:
                    plugin_markdown += f"\n  用法: {matcher_data.usage}"
                plugin_markdown += "\n"
        menu_datas.append(plugin_markdown.strip())

    return menu_datas
