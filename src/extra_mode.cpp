#include "generated/default/psu_init.h"
#include <atomic>
#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_BOOL(psu_unlock_extra_mode, true, "PSU",
                    "Unlock offline Extra Mode and its story-gated missions without changing story saves");
REXCVAR_DEFINE_BOOL(psu_trace_extra_mode, false, "PSU", "Log Extra Mode availability queries");

// Verified USA/Europe XEX: seq.open_ex_mode (822F7980) writes the save manager's
// +52B8 flag through 8225F988. Override its reader, never the flag or its setter.
REX_EXTERN(__imp__sub_8225FE40);
REX_EXTERN(sub_8225FE40) {
  __imp__sub_8225FE40(ctx, base);
  const auto saved = ctx.r3.u32;
  if (REXCVAR_GET(psu_unlock_extra_mode)) ctx.r3.u64 = 1;
  static std::atomic<unsigned> reported{0};
  if (REXCVAR_GET(psu_trace_extra_mode) && reported.fetch_add(1) < 8)
    REXLOG_INFO("PSU Extra Mode access: saved={} effective={}", saved, ctx.r3.u32);
}

// Per-location Extra Mode chapter ceiling. seq.set_ex_chapter_no clamps this to
// 11 (zero-based Chapter 12). Only the returned ceiling changes; slot contents,
// character level, mission rank/level requirements and story chapter stay intact.
// The campaign's setter also calls this reader before recording real progress.
// Preserve that comparison so disabling the option later restores genuine unlocks.
REX_EXTERN(__imp__sub_8225FDE8);
REX_EXTERN(sub_8225FDE8) {
  const auto caller = static_cast<uint32_t>(ctx.lr);
  __imp__sub_8225FDE8(ctx, base);
  const auto saved = ctx.r3.s32;
  if (REXCVAR_GET(psu_unlock_extra_mode) && caller != 0x82305FC4)
    ctx.r3.s64 = 11;
  static std::atomic<unsigned> reported{0};
  if (REXCVAR_GET(psu_trace_extra_mode) && reported.fetch_add(1) < 16)
    REXLOG_INFO("PSU Extra Mode chapter: caller={:08X} saved={} effective={}",
                caller, saved, ctx.r3.s32);
}
