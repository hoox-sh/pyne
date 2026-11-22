# Object-mode forcing sites — enumeration (as instrumented 2026-11-18)


Instrumentation: every `self.object_mode = True` in `src/pynescript/compiler/compiler.py` was
replaced by `_om_trace(self)` (module-level env-gated helper; see git diff for `src/pynescript/compiler/compiler.py`
and `src/pynescript/compiler/engine.py`). 187 sites total. Line numbers refer to the instrumented
worktree state (uncommitted). `site` recorded by the tracer is `<enclosing_function>:<line>`.

Families: {'string': 25, 'udt': 19, 'array': 18, 'misc': 15, 'drawing': 14, 'udf': 10, 'namespace': 10, 'strategy': 10, 'library': 9, 'coercion': 7, 'timeframe': 7, 'switch-if': 6, 'color': 6, 'math': 6, 'map': 5, 'request': 5, 'input': 4, 'syminfo': 4, 'enum': 3, 'residual': 1, 'tuple': 1, 'plot': 1, 'runtime-error': 1}

| line | enclosing def | label | family |
|---:|---|---|---|
| 1134 | `_materialize_series_source` | object-dtype series source materialized for TA kernel (store_src_py) | coercion |
| 1194 | `_visit_import_inner` | import <lib> statement (library import) | library |
| 1445 | `visit_Script` | compile-end residual: object-typed series/scalars remain (string/UDT/map/handles) | residual |
| 1447 | `visit_Script` | force_object_mode (engine nopython-recovery re-emit; not hit in this scan) | misc |
| 1455 | `visit_Script` | varip present (numeric nopython cannot honor per-tick rollback) | misc |
| 1713 | `_emit_alert_call` | alert()/alertcondition() call | misc |
| 1760 | `_alloc_once_flag` | in-function `once` flag (UDF once-semantics) | udf |
| 1952 | `visit_TypeDef` | UDT type declaration | udt |
| 1977 | `visit_EnumDef` | enum declaration | enum |
| 2397 | `_emit_assigned_hline` | assigned hline: price not provably numeric | drawing |
| 2648 | `visit_Assign` | assignment target is an attribute (obj.field := …) | udt |
| 2678 | `visit_Assign` | enum-typed variable declaration | enum |
| 2816 | `visit_Assign` | typed declaration: collection/UDT/chart.point/map/stringy | misc |
| 2833 | `visit_Assign` | map.new / typed map declaration | map |
| 2841 | `visit_Assign` | RHS is a sequence (array/list handle) | array |
| 2853 | `visit_Assign` | UDT-typed local (ctor/dict/call-returned) | udt |
| 2867 | `visit_Assign` | assignment target shadows a UDF (local rename) | udf |
| 2877 | `visit_Assign` | var drawing/collection handle declared na | drawing |
| 2901 | `visit_Assign` | var UDT/chart.point declared na | udt |
| 2919 | `visit_Assign` | RHS is sequence/list (series position) | array |
| 2949 | `visit_Assign` | string constant RHS | string |
| 2977 | `visit_Assign` | stringy RHS (expr classifies as string) | string |
| 3006 | `visit_Assign` | reassign of known string_series variable | string |
| 3022 | `visit_Assign` | map.new / typed map (series position) | map |
| 3047 | `visit_Assign` | RHS is UDT/object-handle expression | udt |
| 3064 | `visit_Assign` | drawing constructor/handle RHS | drawing |
| 3072 | `visit_Assign` | array/matrix handle RHS | array |
| 3099 | `visit_Assign` | sequence-producing RHS | array |
| 3108 | `visit_Assign` | safe_float/safe_int-wrapped RHS (cast hides object value) | coercion |
| 3127 | `visit_Assign` | catch-all: unclassified non-numeric RHS in assignment | misc |
| 4031 | `_visit_tuple_assign` | tuple target element shadows UDF (local rename) | udf |
| 4057 | `_visit_tuple_assign` | tuple element shadows UDF (__loc rename) | udf |
| 4064 | `_visit_tuple_assign` | tuple element is stringy (multi-return strings) | string |
| 4076 | `_visit_tuple_assign` | tuple element kept as object (UDT/string/sequence) | udt |
| 4099 | `_visit_tuple_assign` | tuple element is sequence/array | array |
| 4187 | `_visit_tuple_assign` | multi-target from security()/complex call | request |
| 4213 | `_visit_tuple_assign` | tuple assign from empty/stub call result | library |
| 4320 | `_visit_tuple_assign` | multi-target from non-numeric UDF call | udf |
| 4353 | `_visit_tuple_assign` | tuple assign from if-expression (statement form) | switch-if |
| 4358 | `_visit_tuple_assign` | tuple assign from multiline/if RHS | switch-if |
| 4364 | `_visit_tuple_assign` | tuple assign: multi-name unpack | tuple |
| 4447 | `visit_ReAssign` | reassign target is an attribute (obj.field :=) | udt |
| 4488 | `visit_ReAssign` | reassign RHS: object/string/UDT/sequence expr | udt |
| 4533 | `visit_ReAssign` | reassign to scalar/map/drawing var with drawing handle | drawing |
| 4538 | `visit_ReAssign` | reassign to string_series/udt variable | string |
| 4543 | `visit_ReAssign` | UDT reference rebind (a := b) | udt |
| 4553 | `visit_ReAssign` | reassign: object-handle RHS | udt |
| 4559 | `visit_ReAssign` | reassign: sequence RHS into series slot | array |
| 4573 | `visit_ReAssign` | reassign: value not safe-numeric (series store) | coercion |
| 4576 | `visit_ReAssign` | reassign: sequence/UDT-dict into series store | coercion |
| 4618 | `visit_AugAssign` | aug-assign target is an attribute | udt |
| 4665 | `visit_Name` | bare `tickerid`/`ticker` builtin | namespace |
| 4687 | `visit_Name` | bare `color` namespace used as value | color |
| 4730 | `visit_Name` | bare `tz` builtin | namespace |
| 4734 | `visit_Name` | bare color-name constant (red, green, …) | color |
| 4739 | `visit_Name` | bare linestyle identifier | namespace |
| 4753 | `visit_Name` | timeframe_* unknown-attr fallback | timeframe |
| 4789 | `visit_Name` | namespace used as a value | namespace |
| 4792 | `visit_Name` | stub-namespace (_STUB_NS) used as a value | namespace |
| 4799 | `visit_Name` | bare type name used as a value | namespace |
| 4826 | `visit_Name` | import alias used as a value | library |
| 4842 | `visit_Attribute` | input.* stringy token (type=input.color/symbol/…) | input |
| 4883 | `visit_Attribute` | alert.freq_* attribute | misc |
| 4921 | `visit_Attribute` | drawing `.all` attr (linefill/table/…) | drawing |
| 5010 | `visit_Attribute` | dividends/currency/earnings/splits stub attr | namespace |
| 5034 | `visit_Attribute` | user enum member (incl. hoisted fwd ref) | enum |
| 5048 | `visit_Attribute` | UDT type-name attr read (field access) | udt |
| 5073 | `visit_Attribute` | strategy.opentrades.capital_held | strategy |
| 5077 | `visit_Attribute` | strategy.closedtrades.first_index | strategy |
| 5093 | `visit_Attribute` | chained UDT field read (walrus/udt_get_field) | udt |
| 5099 | `visit_Attribute` | field read on call result | udt |
| 5108 | `visit_Attribute` | field read on call-ish expression | udt |
| 5112 | `visit_Attribute` | field read when already object_mode / udt var (fast path) | udt |
| 5151 | `visit_Attribute` | unknown member attr (catch-all) | namespace |
| 5694 | `_emit_strategy_attr` | strategy.* series attr (equity, openprofit, …) | strategy |
| 5715 | `_emit_strategy_attr` | strategy direction/avg_price attrs | strategy |
| 5724 | `_emit_strategy_attr` | strategy oca/commission/direction/risk attr | strategy |
| 5753 | `_timeframe_compile_expr` | timeframe.in_seconds() | timeframe |
| 5756 | `_timeframe_compile_expr` | timeframe.* compile-time attr | timeframe |
| 5768 | `_syminfo_compile_expr` | syminfo.ticker | syminfo |
| 5771 | `_syminfo_compile_expr` | syminfo.tickerid / syminfo.root | syminfo |
| 5774 | `_syminfo_compile_expr` | syminfo.prefix | syminfo |
| 5792 | `_syminfo_compile_expr` | syminfo string/chart stub attr | syminfo |
| 5900 | `visit_Call` | UDT Type.copy() | udt |
| 5919 | `visit_Call` | UDT instance.copy() | udt |
| 5955 | `visit_Call` | array/matrix method call (method form) | array |
| 5968 | `visit_Call` | drawing method call (method form) | drawing |
| 5995 | `visit_Call` | array/matrix method call (receiver branch) | array |
| 6008 | `visit_Call` | map method call | map |
| 6017 | `visit_Call` | chart.point.* call | misc |
| 6024 | `visit_Call` | drawing .copy() call | drawing |
| 6033 | `visit_Call` | collection method call (generic branch) | array |
| 6037 | `visit_Call` | map method call (generic branch) | map |
| 6041 | `visit_Call` | table method call | drawing |
| 6052 | `visit_Call` | library import method call | library |
| 6137 | `visit_Call` | bare collection verb (push/put/cell) | array |
| 6171 | `visit_Call` | chart.point constructor | misc |
| 6230 | `visit_Call` | modify()/ticker_modify call | request |
| 6238 | `visit_Call` | ticker.new | namespace |
| 6249 | `visit_Call` | ticker.* | namespace |
| 6262 | `visit_Call` | library() declaration | library |
| 6267 | `visit_Call` | strategy() declaration | strategy |
| 6300 | `visit_Call` | input.color/symbol/timeframe/session | input |
| 6306 | `visit_Call` | input.string/text_area (no defval) | input |
| 6316 | `visit_Call` | input.color/symbol/timeframe/session (second branch) | input |
| 6365 | `visit_Call` | hline() with non-numeric price | drawing |
| 6410 | `visit_Call` | fill() with non-numeric price/series | drawing |
| 6471 | `visit_Call` | plot() of string/UDT series | plot |
| 6506 | `visit_Call` | drawing setters (*_set_*/table_set_*/table_cell) | drawing |
| 6538 | `visit_Call` | drawing getters (label_get_*/line_get_*/box_get_*) | drawing |
| 6567 | `visit_Call` | drawing constructor (label/line/box/table/polyline) | drawing |
| 6572 | `visit_Call` | map.* call | map |
| 6583 | `visit_Call` | array.*/matrix.* call | array |
| 6589 | `visit_Call` | console.* call | misc |
| 6605 | `visit_Call` | runtime.error non-literal / multi-arg | runtime-error |
| 6611 | `visit_Call` | color.from_gradient | color |
| 6626 | `visit_Call` | color.new/color() outside literal-fold context (e.g. assignment) | color |
| 6657 | `visit_Call` | color.new literal fold failed | color |
| 6668 | `visit_Call` | timeframe.from_seconds | timeframe |
| 6684 | `visit_Call` | timeframe.change with calendar timeframe | timeframe |
| 6691 | `visit_Call` | timeframe.change (generic/bucket) | timeframe |
| 6733 | `visit_Call` | UDF called as method with 0 formals | udf |
| 6751 | `visit_Call` | table_set_* direct call | drawing |
| 6757 | `visit_Call` | str.split | string |
| 6764 | `visit_Call` | sequence.from_series | array |
| 6772 | `visit_Call` | str.tostring / tostring | string |
| 6775 | `visit_Call` | str.format | string |
| 6783 | `visit_Call` | str.length | string |
| 6786 | `visit_Call` | str.contains | string |
| 6791 | `visit_Call` | str.startswith | string |
| 6796 | `visit_Call` | str.endswith | string |
| 6801 | `visit_Call` | str.replace/str.replace_all | string |
| 6806 | `visit_Call` | str.lower | string |
| 6809 | `visit_Call` | str.upper | string |
| 6812 | `visit_Call` | str.trim | string |
| 6815 | `visit_Call` | str.repeat | string |
| 6821 | `visit_Call` | str.format_time | string |
| 6826 | `visit_Call` | str.tonumber / tonumber | string |
| 6831 | `visit_Call` | str.substring / substring | string |
| 6842 | `visit_Call` | str.pos | string |
| 6847 | `visit_Call` | str.startswith (alias) | string |
| 6852 | `visit_Call` | str.endswith (alias) | string |
| 6858 | `visit_Call` | sequence.from_series (library) | array |
| 6867 | `visit_Call` | sequence.float | array |
| 6878 | `visit_Call` | index_2d_to_1d / index_1d_to_2d | array |
| 6904 | `visit_Call` | alert() with named/positional args (active alert) | misc |
| 6930 | `visit_Call` | timeframe() unparseable argument | timeframe |
| 6960 | `visit_Call` | request.security with UDT result | request |
| 6966 | `visit_Call` | request.footprint | misc |
| 6969 | `visit_Call` | request.* (other) | request |
| 6973 | `visit_Call` | footprint_* call | misc |
| 6981 | `visit_Call` | volume_row_* call | misc |
| 7825 | `visit_Call` | nz() with non-numeric arg/replacement | coercion |
| 7836 | `visit_Call` | fixnan with stringy/series arg | coercion |
| 7842 | `visit_Call` | complex.new / complex_arr_new | misc |
| 7910 | `visit_Call` | math.round unsafe (or already object_mode) | math |
| 7923 | `visit_Call` | math.round_to_mintick unsafe | math |
| 7942 | `visit_Call` | math.avg single-arg unsafe | math |
| 7947 | `visit_Call` | math.avg multi-arg unsafe | math |
| 7962 | `visit_Call` | color.rgb | color |
| 8018 | `visit_Call` | float()/na-like cast of non-numeric arg | coercion |
| 8034 | `visit_Call` | string() cast | string |
| 8041 | `visit_Call` | math.todegrees unsafe | math |
| 8047 | `visit_Call` | math.toradians unsafe | math |
| 8053 | `visit_Call` | library stub init() (init/console_init) | library |
| 8064 | `visit_Call` | library stub (hsl_to_rgb/perceptron/layer/activation/…) | library |
| 8067 | `visit_Call` | array.range | array |
| 8077 | `visit_Call` | unknown call → object-mode stub | library |
| 8543 | `_emit_strategy_call` | strategy.* call | strategy |
| 8648 | `_emit_strategy_risk_call` | strategy.risk.* call | strategy |
| 8684 | `_emit_strategy_trade_query` | strategy.opentrades/closedtrades call | strategy |
| 8734 | `_emit_udt_new` | UDT.new() constructor | udt |
| 9236 | `visit_BinOp` | BinOp with a stringy operand | string |
| 9249 | `visit_BinOp` | BinOp name+name add inside UDF | misc |
| 9677 | `_emit_chart_htf_security` | request.security HTF (chart) | request |
| 9769 | `visit_Subscript` | subscript on sequence/scalar/param | array |
| 9857 | `visit_Subscript` | subscript of strategy history series | strategy |
| 10007 | `visit_Switch` | switch with multi-statement arms | switch-if |
| 10045 | `visit_Switch` | switch statement form | switch-if |
| 10199 | `_coerce_if_assign_val` | if-assign coercion, non-numeric value | switch-if |
| 10268 | `_emit_switch_assign` | switch tuple-assign | switch-if |
| 10517 | `visit_FunctionDef` | library export/method def | library |
| 10702 | `visit_FunctionDef` | function returns UDT | udf |
| 10812 | `visit_FunctionDef` | function uses drawings (__drawings) | udf |
| 10878 | `visit_FunctionDef` | function uses data_feed/data_provider | udf |
| 10884 | `visit_FunctionDef` | function uses __strategy | udf |
| 11655 | `visit_ForIn` | for..in over collection | array |

Total: 187 instrumented forcing sites.
