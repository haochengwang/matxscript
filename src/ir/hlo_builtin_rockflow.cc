// Copyright 2022 ByteDance Ltd. and/or its affiliates.
/*
 * Acknowledgement: The structure of the expressions is inspired by TVM.
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
#include <matxscript/ir/hlo_builtin.h>
#include "./hlo_builtin_macros.h"

namespace matxscript {
namespace ir {
namespace builtin {

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_int, GetInt)
    .set_num_inputs(3)
    .add_argument("self", "RockflowContext", "")
    .add_argument("attr_name", "bytes", "")
    .add_argument("default_value", "int", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_double, GetDouble)
    .set_num_inputs(3)
    .add_argument("self", "RockflowContext", "")
    .add_argument("attr_name", "bytes", "")
    .add_argument("default_value", "float", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_string, GetString)
    .set_num_inputs(3)
    .add_argument("self", "RockflowContext", "")
    .add_argument("attr_name", "bytes", "")
    .add_argument("default_value", "bytes", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_int_list, GetIntList)
    .set_num_inputs(2)
    .add_argument("self", "RockflowContext", "")
    .add_argument("attr_name", "bytes", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_double_list, GetDoubleList)
    .set_num_inputs(2)
    .add_argument("self", "RockflowContext", "")
    .add_argument("attr_name", "bytes", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_string_list, GetStringList)
    .set_num_inputs(2)
    .add_argument("self", "RockflowContext", "")
    .add_argument("attr_name", "bytes", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_item_count, GetItemCount)
    .set_num_inputs(1)
    .add_argument("self", "RockflowContext", "");

MATXSCRIPT_IR_DEFINE_HLO_METHOD(rockflow_context, get_item_attr_assigner, GetItemAttrAssigner)
    .set_num_inputs(2)
    .add_argument("self", "RockflowContext", "")
    .add_argument("index", "int", "");

}  // namespace builtin
}  // namespace ir
}  // namespace matxscript

