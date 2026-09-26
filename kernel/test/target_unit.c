// SPDX-License-Identifier: Apache-2.0
/* One translation unit for lowering the actual kernel entry consumer. Build
 * capacities are supplied by the composition; there is no host-model define. */
#include "vos_target.h"
#include "../src/context.c"
#include "../src/executive.c"
#include "../src/partition.c"
#include "../src/handoff.c"
#include "../src/target.c"
