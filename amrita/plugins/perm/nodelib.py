import json
from copy import deepcopy
from typing import Any

from typing_extensions import Self


class Permissions:
    permissions_data: dict[str, str | dict | bool]
    node_dict: dict[str, bool]
    __permissions_str: str = ""

    def __init__(
        self, permissions_data: dict[str, str | dict | bool] | None = None
    ) -> None:
        if permissions_data is None:
            permissions_data = {}
        self.permissions_data = permissions_data
        self.node_dict = {}
        self.__dump()

    def __str__(self):
        return json.dumps(self.permissions_data)

    def __search_perm(
        self, data: dict[str, Any], parent_key="", result=None
    ) -> list[tuple[str, bool]]:
        if result is None:
            result = []

        for key, node in data.items():
            current_path = f"{parent_key}.{key}" if parent_key else key

            # 检查当前节点权限
            if node.get("has_permission", False):
                result.append((current_path, True))
            elif node.get("explicit_hasnt", False):
                result.append((current_path, False))
            if node.get("children", {}) != {}:
                children = node.get("children", {})
                self.__search_perm(children, current_path, result)
        return result

    def __dump(
        self,
        overwrite: bool = False,
    ):
        if overwrite:
            self.__permissions_str = ""
        data = self.permissions_data
        data = deepcopy(data)
        node_dict = {}
        for n, v in self.__search_perm(data):
            self.__permissions_str += f"{n} {'true' if v else 'false'}\n"
            node_dict[n] = v
        self.node_dict = node_dict

    def del_permission(self, node: str) -> Self:
        node_parts = node.split(".")
        current_children: dict[str, Any] = self.permissions_data  # 当前层级的子节点字典
        try:
            for i, part in enumerate(node_parts):
                if part not in current_children:
                    return self  # 节点不存在，无法删除
                current_node = current_children[part]
                if i == len(node_parts) - 1:
                    del current_children[part]
                current_children = current_node["children"]
        finally:
            self.__dump(overwrite=True)
        return self

    def set_permission(
        self, node: str, has_permission: bool, has_parent: bool = False
    ) -> Self:
        node_parts = node.split(".")
        current_children: dict[str, Any] = self.permissions_data  # 当前层级的子节点字典

        for i, part in enumerate(node_parts):
            # 不存在创建新节点
            if part not in current_children:
                current_children[part] = {
                    "has_permission": has_parent,
                    "children": {},
                    "explicit_hasnt": False,
                }
            current_node = current_children[part]
            # 最后一个部分设权
            if i == len(node_parts) - 1:
                current_node["has_permission"] = has_permission
                current_node["explicit_hasnt"] = not has_permission
            # 下一层
            current_children = current_node["children"]
        self.__dump(overwrite=True)
        return self

    def check_permission(self, node: str) -> bool:
        node = node.strip()
        node_dict = self.node_dict
        if node_dict.get(node):
            return True
        current_node = ""
        for part in node.split("."):
            if node_dict.get(f"{current_node}.*"):
                return True
            current_node += ("." if current_node else "") + part
            if node_dict.get(current_node):
                return True
        return False

    def dump_to_file(self, filename: str):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.permissions_data, f, indent=4)
        self.__dump(overwrite=True)

    def load_from_json(self, filename: str):
        with open(filename, encoding="utf-8") as f:
            self.permissions_data = json.load(f)
        self.__dump(overwrite=True)

    def from_perm_str(self, perm_str: str):
        for line in perm_str.split("\n"):
            if line.strip() == "":
                continue
            node, permission = line.split(" ")
            self.set_permission(node.strip(), permission.strip().lower() == "true")

    def dump_data(self) -> dict[str, Any]:
        return self.permissions_data.copy()

    @property
    def data(self) -> dict[str, Any]:
        return self.permissions_data.copy()

    @data.setter
    def data(self, data: dict[str, Any]):
        self.permissions_data = data
        self.__dump(overwrite=True)

    @property
    def perm_str(self) -> str:
        return self.permissions_str

    @property
    def permissions_str(self) -> str:
        self.__dump(True)
        return self.__permissions_str


# 此处仅用于测试
if __name__ == "__main__":
    permissions = Permissions()
    permissions.set_permission("user.*", True)
    print(permissions.check_permission("user.a"))
    print(permissions.permissions_str)
    print(json.dumps(permissions.dump_data(), indent=4))
    print(permissions.node_dict)
