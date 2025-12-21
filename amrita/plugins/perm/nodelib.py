import json

from typing_extensions import Self


class Permissions:
    permissions_data: dict[str, bool]
    __permissions_str: str = ""

    def __init__(self, permissions_data: dict[str, bool] | None = None) -> None:
        """
        初始化 Permissions 对象

        Args:
            permissions_data: 权限数据字典，键为权限节点路径，值为布尔值表示是否拥有权限
        """
        if permissions_data is None:
            permissions_data = {}
        self.permissions_data = permissions_data
        self.__write_to_string()

    def __str__(self):
        return json.dumps(self.permissions_data)

    def __write_to_string(self, overwrite: bool = False):
        """
        将权限数据转储为字符串形式

        Args:
            overwrite: 是否覆盖现有字符串
        """
        if overwrite:
            self.__permissions_str = ""

        permissions_str = ""
        for node, permission in self.permissions_data.items():
            permissions_str += f"{node} {'true' if permission else 'false'}\n"
        self.__permissions_str = permissions_str

    def del_permission(self, node: str) -> Self:
        """
        删除指定节点的权限

        Args:
            node: 权限节点路径

        Returns:
            Self: 返回自身以支持链式调用
        """
        if node in self.permissions_data:
            del self.permissions_data[node]
            self.__write_to_string(overwrite=True)
        return self

    def set_permission(self, node: str, has_permission: bool) -> Self:
        """
        设置指定节点的权限

        Args:
            node: 权限节点路径
            has_permission: 是否拥有权限

        Returns:
            Self: 返回自身以支持链式调用
        """
        self.permissions_data[node] = has_permission
        self.__write_to_string(overwrite=True)
        return self

    def check_permission(self, node: str) -> bool:
        """
        检查是否拥有指定节点的权限

        Args:
            node: 权限节点路径

        Returns:
            bool: 是否拥有权限
        """
        node = node.strip()
        if self.permissions_data.get(node):
            return True

        current_node = ""
        for part in node.split("."):
            if self.permissions_data.get(f"{current_node}.*"):
                return True
            current_node += ("." if current_node else "") + part
            if self.permissions_data.get(current_node):
                return True
        return False

    def dump_to_file(self, filename: str):
        """
        将权限数据导出到文件

        Args:
            filename: 文件名
        """
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.permissions_data, f, indent=4)
        self.__write_to_string(overwrite=True)

    def load_from_json(self, filename: str):
        """
        从 JSON 文件加载权限数据

        Args:
            filename: 文件名
        """
        with open(filename, encoding="utf-8") as f:
            self.permissions_data = json.load(f)
        self.__write_to_string(overwrite=True)

    def from_perm_str(self, perm_str: str):
        """
        从权限字符串加载权限数据

        Args:
            perm_str: 权限字符串
        """
        self.permissions_data = {}
        for line in perm_str.split("\n"):
            if line.strip() == "":
                continue
            parts = line.split(" ")
            if len(parts) >= 2:
                node, permission = parts[0], parts[1]
                self.permissions_data[node.strip()] = (
                    permission.strip().lower() == "true"
                )
        self.__write_to_string(overwrite=True)

    def dump_data(self) -> dict[str, bool]:
        """
        导出权限数据

        Returns:
            dict: 权限数据副本
        """
        return self.permissions_data.copy()

    @property
    def data(self) -> dict[str, bool]:
        """
        获取权限数据

        Returns:
            dict: 权限数据副本
        """
        return self.permissions_data.copy()

    @data.setter
    def data(self, data: dict[str, bool]):
        """
        设置权限数据

        Args:
            data: 新的权限数据
        """
        self.permissions_data = data
        self.__write_to_string(overwrite=True)

    @property
    def perm_str(self) -> str:
        """
        获取权限字符串表示

        Returns:
            str: 权限字符串
        """
        return self.permissions_str

    @property
    def permissions_str(self) -> str:
        """
        获取权限字符串表示

        Returns:
            str: 权限字符串
        """
        self.__write_to_string(True)
        return self.__permissions_str


# 此处仅用于测试
if __name__ == "__main__":
    permissions = Permissions()
    permissions.set_permission("user.*", True)
    print(permissions.check_permission("user.a"))
    print(permissions.permissions_str)
    print(json.dumps(permissions.dump_data(), indent=4))
