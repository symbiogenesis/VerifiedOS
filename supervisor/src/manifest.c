// SPDX-License-Identifier: Apache-2.0
#include "vos_supervisor.h"

/* M8a source: an immutable typed C object in the admitted supervisor image.
   Local units: 0 crypto-core, 1 storage, 2 copy-service. Only storage's
   crypto-core edge is declared here. No runtime configuration parser. */
const struct vos_supervisor_manifest vos_m8a_supervisor_manifest = {
    3, {0, 1, 2}, {0, 1, 0},
    {3, 3, 3, 3, 3, 3, 3, 3},
    {1, 1, 1, 1, 1, 1, 1, 1},
    {VOS_REFUSE_REQUEST, VOS_REFUSE_REQUEST, VOS_RESTART_SUBTREE,
     VOS_REFUSE_REQUEST, VOS_RESTART_SUBTREE, VOS_FAIL_STOP,
     VOS_REFUSE_REQUEST, VOS_REFUSE_REQUEST},
    2, 3, VOS_FAIL_STOP, 4, {1, 2, 3, 5}, 5, 3, 7
};
