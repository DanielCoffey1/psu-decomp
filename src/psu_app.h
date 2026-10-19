// psu - ReXGlue Recompiled Project
//
// Customize your app by overriding virtual hooks from rex::ReXApp.

#pragma once

#include <rex/rex_app.h>
#include <rex/runtime.h>
#include <rex/memory.h>
#include <fstream>
#include <cstdlib>
#include <rex/ui/imgui_drawer.h>
#include "keyboard_taps.h"

class PsuApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<PsuApp>(new PsuApp(ctx, "psu",
        PPCImageConfig));
  }

  void OnPostLoadXexImage() override {
    // Opt-in local analysis dump, never included in source control.
    char* dump_flag = nullptr;
    size_t dump_flag_size = 0;
    _dupenv_s(&dump_flag, &dump_flag_size, "PSU_DUMP_IMAGE");
    const bool should_dump = dump_flag != nullptr;
    std::free(dump_flag);
    if (should_dump) {
      std::ofstream dump(game_data_root() / "loaded-image.bin", std::ios::binary);
      dump.write(reinterpret_cast<const char*>(runtime()->memory()->virtual_membase() + REX_IMAGE_BASE), REX_IMAGE_SIZE);
    }
  }

  void OnPreSetup(rex::RuntimeConfig& config) override {
    if (config.gpu_plugin.empty()) config.gpu_plugin = "psu";
  }

  void OnPostSetup() override {
    InstallPsuKeyboardTaps(runtime()->input_system(), window(), [this] {
      auto* drawer = runtime()->imgui_drawer();
      return !drawer || (!drawer->GetIO().WantCaptureKeyboard && !drawer->GetIO().WantCaptureMouse);
    });
  }

  // Override virtual hooks for customization:
  // void OnPostInitLogging() override {}
  // void OnPreSetup(rex::RuntimeConfig& config) override {}
  // void OnLoadXexImage(std::string& xex_image) override {}
  // void OnPostLoadXexImage() override {}
  // void OnPostSetup() override {}
  // void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override {}
  // std::unique_ptr<rex::ui::ImGuiDialog> CreateAchievementsOverlay() override;
  // std::unique_ptr<rex::ui::AchievementNotificationDialog>
  // CreateAchievementNotificationDialog() override;
  // void OnShutdown() override {}
  // void OnConfigurePaths(rex::PathConfig& paths) override {}
};
