import json
from copy import deepcopy
from typing import Any


class Permissions:
    permissions_data: dict[str, str | dict | bool]

    def __init__(
        self, permissions_data: dict[str, str | dict | bool] | None = None
    ) -> None:
        if permissions_data is None:
            permissions_data = {}
        self.permissions_data = permissions_data

    __permissions_str: str = ""

    def __str__(self):
        return json.dumps(self.permissions_data)

    def __search_perm(self, data, parent_key="", result=None):
        if result is None:
            result = []

        for key in data:
            node = data[key]
            current_path = f"{parent_key}.{key}" if parent_key else key

            # 检查当前节点权限
            if node.get("has_permission", False):
                result.append(f"{current_path} true")
            elif node.get("explicit_hasnt", False):
                result.append(f"{current_path} false")
            if node.get("children", {}) != {}:
                children = node.get("children", {})
                self.__search_perm(children, current_path, result)
        return result

    def __dump_to_str(
        self,
        overwrite: bool = False,
    ):
        if overwrite:
            self.__permissions_str = ""
        data = self.permissions_data
        data = deepcopy(data)
        for d in self.__search_perm(data):
            self.__permissions_str += f"{d}\n"

    def del_permission(self, node: str):
        node_parts = node.split(".")
        current_children: dict[str, Any] = self.permissions_data  # 当前层级的子节点字典
        try:
            for i, part in enumerate(node_parts):
                if part not in current_children:
                    return  # 节点不存在，无法删除
                current_node = current_children[part]
                if i == len(node_parts) - 1:
                    del current_children[part]
                current_children = current_node["children"]
        finally:
            self.__dump_to_str(overwrite=True)

    def set_permission(self, node: str, has_permission: bool, has_parent: bool = False):
        node_parts = node.split(".")
        current_children: dict[str, Any] = self.permissions_data  # 当前层级的子节点字典

        for i, part in enumerate(node_parts):
            # 不存在创建新节点
            if part not in current_children:
                current_children[part] = {"has_permission": has_parent, "children": {}}
            current_node = current_children[part]
            # 最后一个部分设权
            if i == len(node_parts) - 1:
                current_node["has_permission"] = has_permission
                current_node["explicit_hasnt"] = not has_permission
            # 下一层
            current_children = current_node["children"]
        self.__dump_to_str(overwrite=True)

    def check_permission(self, node: str) -> bool:
        node_parts = node.split(".")
        current_children: dict[str, Any] = self.permissions_data  # 当前层级的子节点字典
        current_node = None

        for part in node_parts:
            if part in current_children:
                current_node = current_children[part]
                current_children = current_node["children"]
            elif "*" in current_children:
                current_node = current_children["*"]
                current_children = current_node["children"]
            else:
                return False  # 没有找到节点或通配符

        # 返回最终节点的权限
        return current_node["has_permission"] if current_node else False

    def dump_to_file(self, filename: str):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.permissions_data, f, indent=4)
        self.__dump_to_str(overwrite=True)

    def load_from_json(self, filename: str):
        with open(filename, encoding="utf-8") as f:
            self.permissions_data = json.load(f)
        self.__dump_to_str(overwrite=True)

    def dump_data(self) -> dict[str, Any]:
        return self.permissions_data.copy()

    @property
    def data(self) -> dict[str, Any]:
        return self.permissions_data.copy()

    @data.setter
    def data(self, data: dict[str, Any]):
        self.permissions_data = data
        self.__dump_to_str(overwrite=True)

    @property
    def perm_str(self) -> str:
        return self.permissions_str

    @property
    def permissions_str(self) -> str:
        return self.__permissions_str


# 此处仅用于测试
if __name__ == "__main__":
    permissions = Permissions({})
    permissions.set_permission("user.read", True)
    permissions.set_permission("user.write", True)
    permissions.set_permission("user.*", True)
    permissions.set_permission("user", False)
    permissions.set_permission("children", True)
    permissions.set_permission("children.read", True)
    permissions.set_permission("children.children", True)
    print(permissions.permissions_str)
    print(json.dumps(permissions.dump_data(), indent=4))
