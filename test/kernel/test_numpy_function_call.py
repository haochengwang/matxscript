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
import unittest
import numpy as np
import sympy

import matx
from matx.kernel.kernel_parser import KernelParser
from matx.kernel.compile_linalg import compile_linalg
from matx.kernel.typing import int32, int64, float32


class TestNumpyFunctionCalls(unittest.TestCase):

    def test_sum_op(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int64:
            return np.sum(a)

        # todo check ir structure
        p = KernelParser(foo)
        p.parse()
        print()
        print("=" * 30, "linalg_code", "=" * 30, sep="")
        print()
        print(p.linalg_code())
        print()
        print("=" * 30, "compile and run", "=" * 30, sep="")
        print()
        a = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32)
        matx_a = matx.array.from_numpy(a)
        f = compile_linalg(p)
        np.testing.assert_equal(f(matx_a), foo(a))

    def test_prod_op(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int64:
            return np.prod(a)

        # todo check ir structure
        p = KernelParser(foo)
        p.parse()
        print()
        print("=" * 30, "linalg_code", "=" * 30, sep="")
        print()
        print(p.linalg_code())
        print()
        print("=" * 30, "compile and run", "=" * 30, sep="")
        print()
        a = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32)
        matx_a = matx.array.from_numpy(a)
        f = compile_linalg(p)
        np.testing.assert_equal(f(matx_a), foo(a))
