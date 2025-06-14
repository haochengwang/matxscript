# Copyright 2022 ByteDance Ltd. and/or its affiliates.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from typing import Any
from .constants._sync_mode import ASYNC

from ..native import make_native_object

import sys
matx = sys.modules['matx']


class _CastOpImpl:
    """Impl: Cast image data type to target type, e.g. uint8 to float32
    """

    def __init__(self, device: Any) -> None:
        self.op: matx.NativeObject = make_native_object(
            "VisionCastGeneralOp", device())

    def __call__(self,
                 images: matx.runtime.NDArray,
                 dtype: str,
                 alpha: float = 1.0,
                 beta: float = 0.0,
                 sync: int = ASYNC) -> matx.runtime.NDArray:
        return self.op.process(images, dtype, alpha, beta, sync)


class CastOp:
    """ Cast image data type to target type, e.g. uint8 to float32
    """

    def __init__(self, device: Any) -> None:
        """ Initialize CastOp

        Args:
            device (Any) : the matx device used for the operation
        """
        self.op: _CastOpImpl = matx.script(_CastOpImpl)(device)

    def __call__(self,
                 images: matx.runtime.NDArray,
                 dtype: str,
                 alpha: float = 1.0,
                 beta: float = 0.0,
                 sync: int = ASYNC) -> matx.runtime.NDArray:
        """ Cast image data type to target type. Could apply factor scale and shift at the same time.

        Args:
            images (matx.runtime.NDArray) : target images.
            dtype (str) : target data type that want to convert to, e.g. uint8, float32, etc.
            alpha (float, optional) : scale factor when casting the data type, e.g. cast image from uint8 to float32,
                                      if want to change the value range from [0, 255] to [0, 1], alpha can be set as 1.0/255.
            beta (float, optional) : shift value when casting the data type
            sync (int, optional): sync mode after calculating the output. when device is cpu, the params makes no difference.
                                    ASYNC -- If device is GPU, the whole calculation process is asynchronous.
                                    SYNC -- If device is GPU, the whole calculation will be blocked until this operation is finished.
                                    SYNC_CPU -- If device is GPU, the whole calculation will be blocked until this operation is finished, and the corresponding CPU array would be created and returned.
                                  Defaults to ASYNC.
        Returns:
            List[matx.runtime.NDArray]: converted images

        Example:

        >>> import cv2
        >>> import matx
        >>> from matx.vision import CastOp

        >>> # Get origin_image.jpeg from https://github.com/bytedance/matxscript/tree/main/test/data/origin_image.jpeg
        >>> image = cv2.imread("./origin_image.jpeg")
        >>> device_id = 0
        >>> device_str = "gpu:{}".format(device_id)
        >>> device = matx.Device(device_str)
        >>> # Create a list of ndarrays for batch images
        >>> batch_size = 3
        >>> nds = [matx.array.from_numpy(image, device_str) for _ in range(batch_size)]
        >>> dtype = "float32"
        >>> alpha = 1.0 / 255
        >>> beta = 0.0

        >>> op = CastOp(device)
        >>> ret = op(nds, dtype, alpha, beta)
        """
        return self.op(images, dtype, alpha, beta, sync)
