# Skills package

# Symbol & Header Skills
from src.skills.symbol_header.missing_header import MissingHeaderSkill
from src.skills.symbol_header.undeclared_identifier import UndeclaredIdentifierSkill
from src.skills.symbol_header.java_import import JavaImportSkill
from src.skills.symbol_header.namespace import NamespaceSkill
from src.skills.symbol_header.forward_decl import ForwardDeclSkill
from src.skills.symbol_header.macro_undefined import MacroUndefinedSkill
from src.skills.symbol_header.kbuild_object import KbuildObjectSkill

# Linkage & Dependency Skills
from src.skills.linkage_dependency.symbol_dep import SymbolDepSkill
from src.skills.linkage_dependency.rust_dep import RustDepSkill
from src.skills.linkage_dependency.vtable import VtableSkill
from src.skills.linkage_dependency.multiple_def import MultipleDefSkill
from src.skills.linkage_dependency.variant_mismatch import VariantMismatchSkill
from src.skills.linkage_dependency.visibility import VisibilitySkill

# API & Type Skills
from src.skills.api_type.signature_mismatch import SignatureMismatchSkill
from src.skills.api_type.type_conversion import TypeConversionSkill
from src.skills.api_type.const_mismatch import ConstMismatchSkill
from src.skills.api_type.override_missing import OverrideMissingSkill
from src.skills.api_type.deprecated_api import DeprecatedAPISkill
from src.skills.api_type.version_guard import VersionGuardSkill

# Build Config Skills
from src.skills.build_config.flag_cleaner import FlagCleanerSkill
from src.skills.build_config.permission import PermissionSkill
from src.skills.build_config.blueprint_syntax import BlueprintSyntaxSkill
from src.skills.build_config.gn_scope import GNScopeSkill
from src.skills.build_config.ninja_cache import NinjaCacheSkill

__all__ = [
    # Symbol & Header
    'MissingHeaderSkill',
    'UndeclaredIdentifierSkill',
    'JavaImportSkill',
    'NamespaceSkill',
    'ForwardDeclSkill',
    'MacroUndefinedSkill',
    'KbuildObjectSkill',

    # Linkage & Dependency
    'SymbolDepSkill',
    'RustDepSkill',
    'VtableSkill',
    'MultipleDefSkill',
    'VariantMismatchSkill',
    'VisibilitySkill',

    # API & Type
    'SignatureMismatchSkill',
    'TypeConversionSkill',
    'ConstMismatchSkill',
    'OverrideMissingSkill',
    'DeprecatedAPISkill',
    'VersionGuardSkill',

    # Build Config
    'FlagCleanerSkill',
    'PermissionSkill',
    'BlueprintSyntaxSkill',
    'GNScopeSkill',
    'NinjaCacheSkill',
]
