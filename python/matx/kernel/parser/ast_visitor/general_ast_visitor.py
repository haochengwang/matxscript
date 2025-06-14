#  Copyright 2023 ByteDance Ltd. and/or its affiliates.
#
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.


from __future__ import annotations

import ast
import numbers
from typing import Any, List, Union, TYPE_CHECKING

import numpy as np


import matx.kernel.graphIR as _gir
import matx.kernel.typing.utils as typing_utils
from matx.kernel.func_registery import FUNC_REGISTRY, TEMPLATE_REGISTRY
from matx.kernel.parser.utils import scalar_or_int_var
from matx.kernel.parser.utils import FuncReturnKind

if TYPE_CHECKING:
    from matx.kernel.kernel_parser import FunctionParser


# todo update return
class GeneralAstVisitor(ast.NodeVisitor):

    def __init__(
            self,
            func_parser: 'FunctionParser'):
        self.func_parser = func_parser

        # necessary for reuse script functionality
        self.root_node = self.func_parser.root_node

        # for kernel use
        self.arg_context_table = self.func_parser.arg_context_table
        self.shape_symbol_table = self.func_parser.shape_symbol_table
        self.tmp_scalar_table = self.func_parser.tmp_scalar_table
        self.tmp_ndarray_table = self.func_parser.tmp_ndarray_table
        self.return_ctx = self.func_parser.return_ctx

        self.reads = []

        self.can_inline = True

    def generic_visit(self, node):
        """Override method in ast.NodeVisitor.
        To directly filter out invalidate type of stmt.
        """
        raise NotImplementedError(f'This node is not supported now: {node}')

    def visit(self, node: Any) -> Any:
        """Override method in ast.NodeVisitor"""
        method = "visit_" + node.__class__.__name__
        print(method)
        visitor = getattr(self, method, self.generic_visit)
        visit_res = visitor(node)
        return visit_res

    def visit_Constant(self, node: ast.Constant) -> _gir.Tensor:
        if node.value is None:
            raise SyntaxError("None is not allowed")
        elif isinstance(node.value, int):
            dtypes = ["int8", "int16", "int32", "int64"]
            for dtype in dtypes:
                if np.iinfo(dtype).min <= node.value <= np.iinfo(dtype).max:
                    break
            else:
                raise SyntaxError("int is out of range ")
            const_scalar_ctx = _gir.Scalar(value=node.value, dtype=dtype, is_internal_constant=True)
            self.func_parser.graph_nodes.append(const_scalar_ctx)
            return const_scalar_ctx
        elif isinstance(node.value, float):
            dtypes = ["float16", "float32", "float64"]
            for dtype in dtypes:
                if np.finfo(dtype).min <= node.value <= np.finfo(dtype).max:
                    break
            else:
                raise SyntaxError("int is out of range ")
            const_scalar_ctx = _gir.Scalar(value=node.value, dtype=dtype, is_internal_constant=True)
            self.func_parser.graph_nodes.append(const_scalar_ctx)
            return const_scalar_ctx
        elif isinstance(node.value, numbers.Number):
            dtype = typing_utils.get_dtype_str(node.value)
            const_scalar_ctx = _gir.Scalar(value=node.value, dtype=dtype, is_internal_constant=True)
            self.func_parser.graph_nodes.append(const_scalar_ctx)
            return const_scalar_ctx
        else:
            raise NotImplementedError(f'Unsupported value {node.value}')

    # variables
    def visit_Name(self, node: ast.Name) -> Union[_gir.Node, None]:
        if isinstance(node.ctx, ast.Del):
            raise SyntaxError(f"del {node.id} is not allowed")
        name = node.id
        if name in self.tmp_scalar_table:
            ctx = self.tmp_scalar_table[name]
            return ctx
        if name in self.tmp_ndarray_table:
            ctx = self.tmp_ndarray_table[name]
            return ctx
        if name in self.shape_symbol_table:
            ctx = self.shape_symbol_table[name]
            return ctx
        if name in self.arg_context_table:
            ctx = self.arg_context_table[name]
            return ctx
        return None
        # return node.id

    # Expressions
    def visit_UnaryOp(self, node: ast.UnaryOp) -> _gir.Tensor:
        # todo modify the code below
        operand_ir = self.visit(node.operand)
        op = _gir.UnaryElementWiseOperator(type(node.op))
        result = op(operand_ir)[0]
        self.func_parser.graph_nodes.append(result)
        self.func_parser.graph_nodes.append(op)
        return result

    def visit_BinOp(self, node: ast.BinOp) -> _gir.Tensor:
        lhs_ir = self.visit(node.left)
        rhs_ir = self.visit(node.right)
        op = _gir.BinaryElementWiseOperator(type(node.op))
        result = op(lhs_ir, rhs_ir)[0]
        self.func_parser.graph_nodes.append(result)
        self.func_parser.graph_nodes.append(op)
        return result

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        opname = type(node.op).__name__
        values = [self.visit(v) for v in node.values]
        for i in range(len(values) - 1):
            lhs = values[i]
            rhs = values[i + 1]
            if scalar_or_int_var(lhs) and scalar_or_int_var(rhs):
                op = _gir.BinaryElementWiseOperator(type(node.op))
                t = op(lhs, rhs)[0]
                self.func_parser.graph_nodes.append(t)
                self.func_parser.graph_nodes.append(op)
                values[i + 1] = t
            else:
                raise SyntaxError(f"{lhs} {opname} {rhs} is not supported "
                                  f"because they are not both scalar")
        return values[-1]

    def visit_Compare(self, node: ast.Compare) -> Any:
        lhs = self.visit(node.left)
        comparators = [self.visit(c) for c in node.comparators]
        for i in range(len(comparators)):
            op = node.ops[i]
            opname = type(op).__name__
            rhs = comparators[i]
            if scalar_or_int_var(lhs) and scalar_or_int_var(rhs):
                op = _gir.BinaryElementWiseOperator(type(op))
                lhs = op(lhs, rhs)[0]
                self.func_parser.graph_nodes.append(lhs)
                self.func_parser.graph_nodes.append(op)
            else:
                raise SyntaxError(f"{lhs} {opname} {rhs} is not supported "
                                  f"because they are not both scalar")
        return lhs

    def visit_Slice(self, node: ast.Slice) -> Any:
        if node.lower is None:
            lower = _gir.Scalar(value=0, dtype="int8", is_internal_constant=True)
        else:
            lower = self.visit(node.lower)
        if node.upper is None:
            upper = None
        else:
            upper = self.visit(node.upper)
        if node.step is None:
            step = _gir.Scalar(value=1, dtype="int8", is_internal_constant=True)
        else:
            step = self.visit(node.step)
        return lower, upper, step

    def visit_Subscript(self, node: ast.Subscript, value=None) -> _gir.Tensor:
        if isinstance(node.ctx, (ast.Del, ast.Store)):
            raise SyntaxError(f"del is not allowed")
        value_node = self.visit(node.value)
        sls = self._get_indexing(node.slice, value_node)
        is_indexing = all(not isinstance(s, tuple)
                          for s in sls) and len(sls) == len(value_node.shape())
        if is_indexing:
            git_item_op = _gir.TensorGetItemOperator()
            self.func_parser.graph_nodes.append(git_item_op)
            result = git_item_op(value_node, sls)[0]
        else:
            slice_op = _gir.TensorSliceOperator()
            self.func_parser.graph_nodes.append(slice_op)
            result_shape = self.calculate_slice_shape(value_node, sls)
            result = slice_op(value_node, sls, result_shape)[0]
        self.func_parser.graph_nodes.append(result)
        return result

    def calculate_slice_shape(self, target, sls):
        shape = []
        for e in sls:
            if _gir.utils.is_graph_ir_scalar(e):
                shape.append(1)
            elif not isinstance(e, (tuple, list)):
                raise SyntaxError("slice has to be tuple or list")
            elif all(_gir.utils.is_graph_ir_const_scalar(s) for s in e):
                lower = e[0].value()
                upper = e[1].value()
                step = e[2].value()
                shape.append((upper - lower - 1) // step + 1)
            else:
                lower = e[0]
                upper = e[1]
                step = e[2]
                const_1 = _gir.Scalar(value=1, dtype="int8", is_internal_constant=True)
                self.func_parser.graph_nodes.append(const_1)
                sub_op1 = _gir.BinaryElementWiseOperator(ast.Sub)
                sub_op2 = _gir.BinaryElementWiseOperator(ast.Sub)
                add_op1 = _gir.BinaryElementWiseOperator(ast.Add)
                floor_div = _gir.BinaryElementWiseOperator(ast.FloorDiv)
                self.func_parser.graph_nodes.extend((sub_op1, sub_op2, add_op1, floor_div))
                sub_result1 = sub_op1(upper, lower)[0]
                sub_result2 = sub_op2(sub_result1, const_1)[0]
                add_result = add_op1(step, const_1)[0]
                size = floor_div(sub_result2, add_result)[0]
                self.func_parser.graph_nodes.extend((sub_result1, sub_result2, add_result, size))
                shape.append(size)
        input_shape = target.shape()
        shape.extend(input_shape[len(shape):])
        trim_idx = next((i for i, x in enumerate(shape) if x != 1), len(shape))
        return shape[trim_idx:]

    def _get_indexing(self, sls: Any, target):
        if isinstance(sls, ast.Slice):
            return list(self.visit(sls))
        if not isinstance(sls, ast.Tuple):
            return [self.visit(sls)]
        idx = []
        for e, s in zip(sls.elts, target.shape()):
            rt_ir = self.visit(e)
            if isinstance(rt_ir, tuple) and rt_ir[1] is None:
                rt_ir = list(rt_ir)
                rt_ir[1] = s
                rt_ir = tuple(rt_ir)
            idx.append(rt_ir)
        return idx

    def visit_Assign(self, node: ast.Assign) -> _gir.Node:
        if len(node.targets) > 1:
            raise SyntaxError(f"Assigning multiple is not allowed")
        if not isinstance(node.targets[0], (ast.Name, ast.Subscript)):
            raise SyntaxError(f"Assigning to {type(node.targets)} is not allowed.")
        if isinstance(node.targets[0], ast.Subscript):
            value = self.visit(node.value)
            return self._assign_item(node.targets[0], value)
        value = self.visit(node.value)
        value_type = _gir.utils.convert_to_kernel_type(value)
        target = self.visit(node.targets[0])
        if target is None:
            if typing_utils.is_scalar_type(value_type):
                return self._allocate_scalar(node.targets[0].id, value, value_type)
            if typing_utils.is_ndarray_type(value_type):
                return self._allocate_ndarray(node.targets[0].id, value, value_type)
        else:
            if typing_utils.is_scalar_type(value_type):
                return self._assign_scalar(target.name(), value, node)
            if typing_utils.is_ndarray_type(value_type):
                return self._assign_ndarray(target.name(), value, node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        ann = self.annotation_to_kernel_type(node.annotation)
        value = self.visit(node.value)
        if not isinstance(node.target, (ast.Name, ast.Subscript)):
            raise SyntaxError(f"Assigning to {type(node.target)} is not allowed.")
        if isinstance(node.target, ast.Name):
            if typing_utils.is_scalar_type(ann):
                return self._allocate_scalar(node.target.id, value, ann)
            if typing_utils.is_ndarray_type(ann):
                return self._allocate_ndarray(node.target.id, value, ann)
        # symbol case
        elif isinstance(node.target, ast.Subscript):
            raise NotImplementedError("assigning to ndarray not supported yet")
        else:
            raise SyntaxError(f"not supported node type {type(node.target)}")

    def _assign_item(self, node: ast.Subscript, value):
        target_name = node.value.id
        target_node = self.visit(node.value)
        sls = self._get_indexing(node.slice, target_node)
        is_indexing = all(not isinstance(s, tuple)
                          for s in sls) and len(sls) == len(target_node.shape())
        if not is_indexing:
            raise SyntaxError(f"not supported syntax")
        subscript_op = _gir.TensorSetItemOperator()
        self.func_parser.graph_nodes.append(subscript_op)
        result = subscript_op(target_node, sls, value)[0]
        self.func_parser.graph_nodes.append(result)
        self.tmp_ndarray_table[target_name] = result
        return result

    def _allocate_scalar(self, target_name, value, ann):
        # the name is conflict with args
        if target_name in self.arg_context_table:
            raise SyntaxError(
                f"Reassigning the scalar {target_name} defined in arguments is not allowed")
        # the name is conflict with previous defined scalar
        if target_name in self.tmp_scalar_table:
            t = self.tmp_scalar_table[target_name]
            t = _gir.utils.convert_to_kernel_type(t)
            if t != ann:
                raise SyntaxError(
                    f"Reallocating the scalar {target_name} defined previous is not allowed")
        # make sure it is annotated as scalar
        if not typing_utils.is_scalar_type(ann):
            raise SyntaxError(f"Annotating {target_name} with type {ann} is not allowed.")
        # make sure the annotated type is the same as rhs value
        v_kernel = _gir.utils.convert_to_kernel_type(value)
        if v_kernel != ann:
            if v_kernel.shape != ann.shape:
                raise SyntaxError(
                    f"Assigning {value.kernel_type} to {ann} is not allowed because they have different shapes")
            elif v_kernel.dtype != ann.dtype:
                pass
            else:
                raise SyntaxError(f"Assigning {value.kernel_type} to {ann} is not allowed")
        tmp_scalar_ctx = _gir.Scalar(
            name=target_name,
            dtype=ann.dtype_str(),
            is_internal_constant=True)
        self.tmp_scalar_table[target_name] = tmp_scalar_ctx
        copy_op = _gir.CopyOperator()
        rt = copy_op(tmp_scalar_ctx, value)[0]
        self.func_parser.graph_nodes.append(copy_op)
        self.func_parser.graph_nodes.append(tmp_scalar_ctx)
        return rt

    def _allocate_ndarray(self, target_name, value, ann):
        # the name is conflict with args
        if target_name in self.arg_context_table:
            raise SyntaxError(
                f"Reassigning the ndarray {target_name} defined in arguments is not allowed")
        # the name is conflict with previous defined ndarray
        if target_name in self.tmp_ndarray_table and \
                _gir.utils.convert_to_kernel_type(self.tmp_ndarray_table[target_name]) != ann:
            raise SyntaxError(
                f"Reallocating the ndarray {target_name} defined previous is not allowed")
        # make sure it is annotated as scalar
        if not typing_utils.is_ndarray_type(ann):
            raise SyntaxError(f"Annotating {target_name} with type {ann} is not allowed.")
        # make sure the annotated type is the same as rhs value
        v_kernel = _gir.utils.convert_to_kernel_type(value)
        if v_kernel != ann:
            raise SyntaxError(f"Assigning {v_kernel} to {ann} is not allowed")
        # todo shape marked here may be by scalars.
        tmp_ndarray_ctx = _gir.Tensor(name=target_name, dtype=value.dtype(), shape=value.shape())
        self.tmp_ndarray_table[target_name] = tmp_ndarray_ctx
        copy_op = _gir.CopyOperator()
        rt = copy_op(tmp_ndarray_ctx, value)[0]
        self.func_parser.graph_nodes.append(copy_op)
        self.func_parser.graph_nodes.append(tmp_ndarray_ctx)
        return rt

    def _assign_scalar(self, target_name, value, node):
        # the name is conflict with args
        if target_name in self.arg_context_table:
            raise SyntaxError(
                f"Reassigning scalars {target_name} defined in arguments is not allowed")
        # it has not been defined
        if target_name not in self.tmp_scalar_table:
            raise SyntaxError(
                f"Assigning scalars {target_name} is not allowed because it not defined")
        # node cannot be annotated assign or other (unlikely to be other)
        if not isinstance(node, ast.Assign):
            raise SyntaxError(f"Using annotated assign to assign {target_name} is not allowed "
                              f"since it has already been defined above")
        previous_ctx = self.tmp_scalar_table[target_name]
        if not _gir.utils.is_compatible(previous_ctx, value):
            raise SyntaxError(
                f"the value assigned to {target_name} is not compatible {previous_ctx.dtype()} and {value.dtype()}")
        new_ctx = _gir.Scalar(
            name=f"{target_name}_{self.func_parser.get_new_tmp_var_id()}",
            dtype=previous_ctx.dtype(),
            is_internal_constant=True)
        self.tmp_scalar_table[target_name] = new_ctx
        copy_op = _gir.CopyOperator()
        self.func_parser.graph_nodes.append(copy_op)
        self.func_parser.graph_nodes.append(new_ctx)
        rt = copy_op(new_ctx, value)
        return rt[0]

    def _assign_ndarray(self, target_name, value, node):
        # the name is conflict with args
        if target_name in self.arg_context_table:
            raise SyntaxError(
                f"Reassigning ndarray {target_name} defined in arguments is not allowed")
        # it has not been defined
        if target_name not in self.tmp_ndarray_table:
            raise SyntaxError(
                f"Assigning ndarray {target_name} is not allowed because it not defined")
        # node cannot be annotated assign or other (unlikely to be other)
        if not isinstance(node, ast.Assign):
            raise SyntaxError(f"Using annotated assign to assign {target_name} is not allowed "
                              f"since it has already been defined above")
        previous_ctx = self.tmp_ndarray_table[target_name]
        if not _gir.utils.is_compatible(previous_ctx, value):
            raise SyntaxError(f"the value assigned to {target_name} is not a ndarray")
        new_ctx = _gir.Tensor(
            name=f"{target_name}_{self.func_parser.get_new_tmp_var_id()}",
            dtype=previous_ctx.dtype(),
            shape=previous_ctx.shape()
        )
        self.tmp_ndarray_table[target_name] = new_ctx
        copy_op = _gir.DeepCopyOperator()
        self.func_parser.graph_nodes.append(copy_op)
        self.func_parser.graph_nodes.append(new_ctx)
        rt = copy_op(new_ctx, value)
        return rt[0]

    def visit_If(self, node: ast.If) -> Any:
        """
        test = self.visit(node.test)
        body = [self.visit(s) for s in node.body]
        orelse = [self.visit(s) for s in node.orelse]
        return IfNode(test, body, orelse, self.build_span(node))"""
        raise NotImplementedError("visit_If is not supported yet")

    def visit_Pass(self, node: ast.Pass) -> Any:
        lhs = _gir.Scalar(value=1, is_internal_constant=True)
        rhs = _gir.Scalar(value=2, is_internal_constant=True)
        self.func_parser.graph_nodes.append(lhs)
        self.func_parser.graph_nodes.append(rhs)
        op = _gir.BinaryElementWiseOperator(ast.Add)
        self.func_parser.graph_nodes.append(op)
        result = op(lhs, rhs)[0]
        return result

    def visit_Call(self, node: ast.Call) -> Any:
        func = node.func
        visited_args = [self.visit(a) for a in node.args]
        if isinstance(func, ast.Attribute):
            func_name = func.attr
            package_name = func.value.id
            return self.library_node_dispatcher(package_name, func_name, visited_args)

        if isinstance(func, ast.Name):
            f_obj = self.func_parser.root_node.module.globals.get(func.id)
            if f_obj in TEMPLATE_REGISTRY:
                template = TEMPLATE_REGISTRY[f_obj]
                args_type_list = [_gir.utils.convert_to_kernel_type(i) for i in visited_args]
                func_inspector = template.get_function(args_type_list).graph
            else:
                if func.id not in FUNC_REGISTRY:
                    from matx.kernel.kernel_parser import KernelParser
                    p = KernelParser(f_obj)
                    p.parse()
                func_inspector = FUNC_REGISTRY[id(f_obj)]
        else:
            raise SyntaxError(f"{func} is not supported now")
        self.can_inline = self.can_inline and func_inspector.can_inline
        if func_inspector.can_inline:
            return self._inline_func(func_inspector, visited_args)
        else:
            raise NotImplementedError("only support inline function for now")

    def library_node_dispatcher(self, package_name, func_name, args):
        package = self.func_parser.root_node.module.globals.get(package_name)
        if package is np:
            from ...library import NP_LIB
            func = NP_LIB.get_func(func_name)
            func_node = func()
            result = func_node(*args)
            self.func_parser.graph_nodes.append(func_node)
            self.func_parser.graph_nodes.extend(result)
            return result[0]
        else:
            raise NotImplementedError("only support numpy function for now")

    def _inline_func(self, inspector: 'FunctionParser', args):
        tensors_nodes = (s for s in inspector.graph_input if isinstance(s, _gir.Tensor))
        for arg_node, tensor_node in zip(args, tensors_nodes):
            cp_op = _gir.CopyOperator()
            cp_op(tensor_node, arg_node)
            self.func_parser.graph_nodes.append(cp_op)
            for a_symbol, tensor_symbol in zip(arg_node.shape(), tensor_node.shape()):
                if isinstance(
                        tensor_symbol,
                        _gir.IntVar) and (
                        not isinstance(
                            tensor_symbol,
                            _gir.IntImm)):
                    tensor_symbol._attrs["symbolic_value"] = a_symbol.symbolic_value()
                    tensor_symbol._attrs["name"] = a_symbol._attrs["name"]
        self.func_parser.graph_nodes.extend(inspector.graph_nodes)
        output = inspector.graph_output[0]
        return output

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value = self.visit(node.value)
        attr_name = node.attr
        if not isinstance(value, list):
            return [value, attr_name]
        return [*value, attr_name]

    def visit_Return(self, node: ast.Return) -> Union[None, _gir.Node]:
        if node.value is None:
            return None
        if self.func_parser.func_return_kind.is_void():
            raise SyntaxError("Void function should return nothing")

        rt_ir = self.visit(node.value)
        rt_ir_shape = rt_ir.shape()
        if self.func_parser.func_return_kind.is_template():
            self.func_parser.graph_output.append(rt_ir)
            return rt_ir
        if self.func_parser.func_return_kind.is_dynamic_tensor():
            self.func_parser.return_dtype_str = rt_ir.dtype()
            self.func_parser.return_shape = rt_ir_shape

        if list(rt_ir_shape) != list(self.func_parser.return_shape):
            raise RuntimeError(f"the marked shape {self.func_parser.return_shape} "
                               f"is not equal to {rt_ir_shape}")

        if self.func_parser.func_return_kind.is_static_tensor():
            op = _gir.DeepCopyOperator()
            self.func_parser.graph_nodes.append(op)
            op(self.return_ctx, rt_ir)
            return self.return_ctx
        self.func_parser.graph_output.append(rt_ir)
        return rt_ir

    def visit_Tuple(self, node: ast.Tuple) -> List[_gir.Node]:
        values = []
        for e in node.elts:
            if not isinstance(e, ast.Name):
                raise SyntaxError(f"for now tuple only support symbol")
            if e.id not in self.func_parser.shape_symbol_table:
                raise SyntaxError(f"for now tuple only support symbol")
            s = self.func_parser.shape_symbol_table[e.id]
            values.append(s.symbolic_value())
        return values

    def annotation_to_kernel_type(self, ann):
        if isinstance(ann, ast.Subscript):
            if not isinstance(ann.value, ast.Name):
                raise SyntaxError(
                    f"kernel variable can only be marked with kernel type, but get ann.value is {type(ann.value)}")
            type_name = ann.value.id
            if type_name not in typing_utils.STR_TO_KERNEL_TYPE:
                raise SyntaxError(
                    f"kernel variable can only be marked with kernel type, but get {type_name}")
            kernel_t = typing_utils.STR_TO_KERNEL_TYPE[type_name]
            if not isinstance(ann.slice, ast.Tuple):
                raise SyntaxError(
                    f"kernel variable can only be marked with kernel type, but get ann.slice is {type(ann.slice)}")
            return kernel_t[self.visit(ann.slice)]
        if isinstance(ann, ast.Name):
            type_name = ann.id
            if type_name not in typing_utils.STR_TO_KERNEL_TYPE:
                raise SyntaxError(
                    f"kernel variable can only be marked with kernel type, but get {type_name}")
            return typing_utils.STR_TO_KERNEL_TYPE[type_name]
        raise SyntaxError(
            f"kernel variable can only be marked with kernel type, but get {type(ann)}")
