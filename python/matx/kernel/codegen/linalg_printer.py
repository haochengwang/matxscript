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

from collections import OrderedDict
from itertools import chain
from typing import List, TYPE_CHECKING

import matx.kernel.graphIR as _gir

if TYPE_CHECKING:
    from .graph_ir_printer import GraphIRPrinter


class LinalgGenericPrinter:
    lingalg_head = "linalg.generic {{indexing_maps = [{}], \n\t\t\t\titerator_types = [{}]}}"
    ins = "\tins({})"
    outs = "\touts({})"

    def __init__(self, node: _gir.ElementWiseOperator, mlir_printer: 'GraphIRPrinter'):
        self.node = node
        self.outputs = set(node.get_outputs())
        self.output_map = OrderedDict()
        self.allocate_stmts: List[str] = []
        self.graph_printer: 'GraphIRPrinter' = mlir_printer

    def add_output(self, out: _gir.Tensor, mlir_name):
        self.outputs.remove(out)
        self.output_map[out] = mlir_name

    def ok_to_generic(self):
        return len(self.outputs) == 0

    def get_inputs(self):
        return self.node.get_inputs()

    def gen_affine_map(self):
        idx = "idx{}"
        inputs = [i for i in self.node.get_inputs() if not _gir.utils.is_graph_ir_scalar(i)]
        outputs = self.node.get_outputs()
        tensor_list = [*inputs, *outputs]
        max_dim = max(len(i.shape()) for i in tensor_list)
        idx_list = [idx.format(i) for i in range(max_dim)]
        affine_map = f"affine_map<({', '.join(idx_list)}) -> ({{}})>"
        affine_maps = [affine_map.format(", ".join(idx_list[-len(t.shape()):]))
                       for t in tensor_list]
        return ", \n\t\t\t\t\t\t\t\t ".join(affine_maps), ", ".join(['"parallel"'] * len(idx_list))

    def gen_in_array(self):
        inputs = [i for i in self.node.get_inputs() if not _gir.utils.is_graph_ir_scalar(i)]
        names = [self.graph_printer.mlir_var_map[i] for i in inputs]
        types = [self.graph_printer.convert_type_to_mlir(i) for i in inputs]
        return f"{', '.join(names)} : {', '.join(types)}"

    def gen_out_array(self):
        outputs = self.node.get_outputs()
        names = [self.output_map[i] for i in outputs]
        types = [self.graph_printer.convert_type_to_mlir(i) for i in outputs]
        return f"{', '.join(names)} : {', '.join(types)}"

    def print_compute_func(self):
        self.graph_printer.mlir_printer.print("{")
        self.graph_printer.mlir_printer.new_scope()
        input_args: List[_gir.Scalar] = [self.node.sub_graph_input[i] for i in self.node.get_inputs(
        ) if i in self.node.sub_graph_input and not _gir.utils.is_graph_ir_scalar(i)]
        output_args: List[_gir.Scalar] = list(self.node.sub_graph_outputs.keys())
        arg_names = []
        for a in chain(input_args, output_args):
            new_var_name = self.graph_printer.new_var_name
            self.graph_printer.mlir_var_map[a] = new_var_name
            arg_names.append(new_var_name)
        input_arg_types = [self.graph_printer.convert_type_to_mlir(a) for a in input_args]
        output_arg_types = [self.graph_printer.convert_type_to_mlir(a) for a in output_args]
        arg_types = chain(input_arg_types, output_arg_types)
        arg_str = f"^bb0({', '.join(f'{a}: {t}' for a, t in zip(arg_names, arg_types))}):"
        self.graph_printer.mlir_printer.print(arg_str)
        self.graph_printer.mlir_printer.new_scope()
        for i in self.node.sub_graph_input.values():
            self.graph_printer.visited.add(i)
        for o in self.node.sub_graph_outputs.keys():
            self.graph_printer.visit(o, None)
        # print here
        yield_stmt = f"linalg.yield {', '.join([self.graph_printer.mlir_var_map[o] for o in output_args])} : " \
                     f"{', '.join(output_arg_types)}"
        self.graph_printer.mlir_printer.print(yield_stmt)
        self.graph_printer.mlir_printer.pop_scope()
        self.graph_printer.mlir_printer.pop_scope()
        self.graph_printer.mlir_printer.print("}")

    def add_allocate_stmt(self, allocate_stmt):
        self.allocate_stmts.append(allocate_stmt)

    def gen_code(self):
        for name, node, stmt in self.allocate_stmts:
            self.graph_printer.mlir_var_map[node] = name
            self.graph_printer.mlir_printer.print(stmt)
        self.allocate_stmts.clear()
        indexing_maps, iterator_types = self.gen_affine_map()
        lingalg_head = self.lingalg_head.format(indexing_maps, iterator_types)
        self.graph_printer.mlir_printer.print(lingalg_head)
        in_array = self.gen_in_array()
        ins = self.ins.format(in_array)
        self.graph_printer.mlir_printer.print(ins)
        out_array = self.gen_out_array()
        outs = self.outs.format(out_array)
        self.graph_printer.mlir_printer.print(outs)
        self.print_compute_func()


class LinalgReductionPrinter:
    scalar_to_memeref = "{} = memref.alloca() : memref<f32>\nmemref.store %0, {}[] : memref<f32>"
    lingalg_head = "linalg.reduce"
    ins = "ins({})"
    outs = "outs({})"
    dimensions = "dimensions = [{}]"

    def __init__(self, node: _gir.ReductionOperator, mlir_printer: 'GraphIRPrinter'):
        self.node = node
        self.graph_printer: 'GraphIRPrinter' = mlir_printer
        self.init_values_map = OrderedDict()
        self.results = []

    def convert_scalar_to_memref(self):
        for out in self.node.sub_graph_init_values:
            mlir_name = self.graph_printer.mlir_var_map[out]
            mlir_type = self.graph_printer.convert_type_to_mlir(out)
            memref_name = self.graph_printer.new_var_name
            memref_type = f"memref<{mlir_type}>"
            self.graph_printer.mlir_printer.print(
                f"{memref_name} = memref.alloca() : {memref_type}")
            self.graph_printer.mlir_printer.print(
                f"memref.store {mlir_name}, {memref_name}[] : {memref_type}")
            self.init_values_map[out] = (memref_name, memref_type)

    def load_from_memref(self):
        for out in self.node.sub_graph_init_values:
            new_name = self.graph_printer.new_var_name
            memref_name, memref_type = self.init_values_map[out]
            self.graph_printer.mlir_printer.print(
                f"{new_name} = memref.load {memref_name}[] : {memref_type}")
            self.graph_printer.mlir_var_map[self.node.results[0]] = new_name
            self.results.append(new_name)

    def gen_in_array(self):
        inputs = [i for i in self.node.get_inputs() if not _gir.utils.is_graph_ir_scalar(i)]
        names = [self.graph_printer.mlir_var_map[i] for i in inputs]
        types = [self.graph_printer.convert_type_to_mlir(i) for i in inputs]
        return f"{', '.join(names)} : {', '.join(types)}"

    def gen_out_array(self):
        outputs = self.node.sub_graph_init_values
        names = [self.init_values_map[i][0] for i in outputs]
        types = [self.init_values_map[i][1] for i in outputs]
        return f"{', '.join(names)} : {', '.join(types)}"

    def print_compute_func(self):
        input_args: List[_gir.Scalar] = [self.node.sub_graph_input[i] for i in self.node.get_inputs(
        ) if i in self.node.sub_graph_input and not _gir.utils.is_graph_ir_scalar(i)]

        init_args: List[_gir.Scalar] = list(self.node.sub_graph_input[i]
                                            for i in self.node.sub_graph_init_values)
        arg_names = []
        for a in chain(input_args, init_args):
            new_var_name = self.graph_printer.new_var_name
            self.graph_printer.mlir_var_map[a] = new_var_name
            arg_names.append(new_var_name)
        input_arg_types = [self.graph_printer.convert_type_to_mlir(a) for a in input_args]
        output_arg_types = [self.graph_printer.convert_type_to_mlir(a) for a in init_args]
        arg_types = chain(input_arg_types, output_arg_types)
        arg_str = f"({', '.join(f'{a}: {t}' for a, t in zip(arg_names, arg_types))}) " + "{"
        self.graph_printer.mlir_printer.print(arg_str)
        self.graph_printer.mlir_printer.new_scope()
        for i in self.node.sub_graph_input.values():
            self.graph_printer.visited.add(i)
        for o in self.node.sub_graph_outputs.keys():
            self.graph_printer.visit(o, None)
        # print here
        yield_vars = ', '.join([self.graph_printer.mlir_var_map[o]
                               for o in self.node.sub_graph_outputs.keys()])
        yield_stmt = f"linalg.yield {yield_vars} : {', '.join(output_arg_types)}"
        self.graph_printer.mlir_printer.print(yield_stmt)
        self.graph_printer.mlir_printer.pop_scope()
        self.graph_printer.mlir_printer.print("}")

    def gen_code(self):
        self.convert_scalar_to_memref()
        self.graph_printer.mlir_printer.print(self.lingalg_head)
        self.graph_printer.mlir_printer.new_scope()
        self.graph_printer.mlir_printer.print(self.ins.format(self.gen_in_array()))
        self.graph_printer.mlir_printer.print(self.outs.format(self.gen_out_array()))
        dims = ", ".join([str(i) for i in self.node.reduction_dims])
        self.graph_printer.mlir_printer.print(self.dimensions.format(dims))
        self.print_compute_func()
        self.graph_printer.mlir_printer.pop_scope()
        self.load_from_memref()
