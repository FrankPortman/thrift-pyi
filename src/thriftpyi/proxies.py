from types import ModuleType
from typing import Dict, List

from thriftpy2.thrift import TPayloadMeta, TType


class InterfaceProxy:
    def __init__(self, module: ModuleType):
        self.module = module

    def get_service(self) -> "ServiceProxy":
        return ServiceProxy(
            [
                member
                for member in self.module.__dict__.values()
                if hasattr(member, "thrift_services")
            ][0]
        )

    def get_imports(self) -> Dict[str, ModuleType]:
        return {
            name: item
            for name, item in self.module.__dict__.items()
            if isinstance(item, ModuleType)
        }

    def get_errors(self) -> List["ExceptionProxy"]:
        return [
            ExceptionProxy(member)
            for name, member in self.module.__dict__.items()
            if isinstance(member, TPayloadMeta) and hasattr(member, "args")
        ]

    def get_enums(self) -> List["EnumProxy"]:
        return [
            EnumProxy(member)
            for name, member in self.module.__dict__.items()
            if hasattr(member, "_NAMES_TO_VALUES")
        ]

    def get_structs(self) -> List["StructProxy"]:
        return [
            StructProxy(member)
            for name, member in self.module.__dict__.items()
            if isinstance(member, TPayloadMeta) and not hasattr(member, "args")
        ]


class StructProxy:
    def __init__(self, tstruct: TPayloadMeta):
        self._tstruct = tstruct
        self.name = tstruct.__name__
        self.module_name = tstruct.__module__

    def get_fields(self) -> List["VarProxy"]:
        return [
            VarProxy(thrift_spec) for thrift_spec in self._tstruct.thrift_spec.values()
        ]


class ExceptionProxy:
    def __init__(self, texc: TPayloadMeta):
        self._texc = texc
        self.name = texc.__name__
        self.module_name = texc.__module__

    def get_fields(self) -> List["FieldProxy"]:
        return [
            FieldProxy(thrift_spec) for thrift_spec in self._texc.thrift_spec.values()
        ]


class EnumFieldProxy:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class EnumProxy:
    def __init__(self, tenum: TPayloadMeta):
        self._tenum = tenum
        self.name = tenum.__name__
        self.module_name = tenum.__module__

    def get_fields(self) -> List["EnumFieldProxy"]:
        fields = self._tenum._NAMES_TO_VALUES  # pylint: disable=protected-access
        return [EnumFieldProxy(name, value) for name, value in fields.items()]


class ServiceProxy:
    def __init__(self, service):
        self.service = service
        self.name = service.__name__
        self.module_name = service.__module__

    def get_methods(self) -> List[str]:
        return [name for name in self.service.thrift_services]

    def get_args_for(self, method_name) -> List["VarProxy"]:
        method_args = getattr(self.service, f"{method_name}_args").thrift_spec.values()
        return [VarProxy(arg) for arg in method_args]

    def get_return_type_for(self, method_name) -> str:
        returns = getattr(self.service, f"{method_name}_result").thrift_spec.get(0)
        if returns is None:
            return "None"
        return VarProxy(returns).reveal_type_for(self.module_name)


class VarProxy:
    def __init__(self, thrift_spec: tuple):
        ttype, name, *meta, _ = thrift_spec
        self._ttype: int = ttype
        self.name: str = name
        self._meta = meta
        self._is_required: bool = True

    def reveal_type_for(self, module_name: str) -> str:
        pytype = _get_python_type(self._ttype, self._is_required, self._meta)
        start, _, end = pytype.rpartition(f"{module_name}.")
        return start + end


class FieldProxy(VarProxy):
    def __init__(self, thrift_spec: tuple):
        super().__init__(thrift_spec)
        self._is_required = thrift_spec[-1]


def _get_python_type(ttype: int, is_required: bool, meta=None) -> str:
    type_map = {
        TType.BOOL: _get_bool,
        TType.DOUBLE: _get_double,
        TType.BYTE: _get_byte,
        TType.I16: _get_i16,
        TType.I32: _get_i32,
        TType.I64: _get_i64,
        TType.STRING: _get_str,
        TType.STRUCT: _get_struct,
        TType.MAP: _get_map,
        TType.SET: _get_set,
        TType.LIST: _get_list,
    }
    pytype = type_map[ttype](meta)
    if not is_required:
        pytype = f"Optional[{pytype}]"
    return pytype


def _get_bool(meta) -> str:
    del meta
    return "bool"


def _get_double(meta) -> str:
    del meta
    return "float"


def _get_byte(meta) -> str:
    del meta
    return "int"


def _get_i16(meta) -> str:
    del meta
    return "int"


def _get_i32(meta) -> str:
    del meta
    return "int"


def _get_i64(meta) -> str:
    del meta
    return "int"


def _get_str(meta) -> str:
    del meta
    return "str"


def _get_struct(meta) -> str:
    return f"{meta[0].__module__}.{meta[0].__name__}"


def _get_list(meta) -> str:
    try:
        subtype, submeta = meta[0]
    except TypeError:
        subtype, submeta = meta[0], None
    return f"List[{_get_python_type(subtype, True, [submeta])}]"


def _get_map(meta) -> str:
    key, value = meta[0]
    key = _get_python_type(key, True)
    value = _get_python_type(value, True)
    return f"Dict[{key}, {value}]"


def _get_set(meta) -> str:
    try:
        subtype, submeta = meta[0]
    except TypeError:
        subtype, submeta = meta[0], None
    return f"Set[{_get_python_type(subtype, True, [submeta])}]"
