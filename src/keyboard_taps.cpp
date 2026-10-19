#include "keyboard_taps.h"
#include <atomic>
#include <array>
#include <chrono>
#include <string_view>
#include <rex/cvar.h>
#include <rex/input/input_system.h>
#include <rex/ui/keybinds.h>
#include <rex/ui/ui_event.h>
#include <rex/logging.h>

REXCVAR_DEFINE_BOOL(psu_trace_input, false, "PSU", "Log keyboard button-edge diagnostics");

namespace {
using rex::X_STATUS;
using rex::X_RESULT;
using namespace rex::input;
constexpr auto kDevice = static_cast<DeviceId>(0x505355544150ull);
bool Enabled() { return rex::cvar::GetFlagByName("mnk_mode") == "true"; }

bool Matches(std::string_view bindings, const rex::ui::KeyEvent& event) {
  const unsigned live = unsigned(event.is_shift_pressed()) |
      (unsigned(event.is_ctrl_pressed()) << 1) | (unsigned(event.is_alt_pressed()) << 2);
  while (!bindings.empty()) {
    const auto comma = bindings.find(',');
    auto token = bindings.substr(0, comma);
    bindings = comma == bindings.npos ? std::string_view{} : bindings.substr(comma + 1);
    while (!token.empty() && token.front() == ' ') token.remove_prefix(1);
    while (!token.empty() && token.back() == ' ') token.remove_suffix(1);
    unsigned wanted = 0;
    for (;;) {
      const auto plus = token.find('+');
      if (plus == token.npos) break;
      const auto modifier = token.substr(0, plus);
      if (modifier == "Shift") wanted |= 1;
      else if (modifier == "Ctrl" || modifier == "Control") wanted |= 2;
      else if (modifier == "Alt") wanted |= 4;
      else break;
      token.remove_prefix(plus + 1);
    }
    if (wanted == live && !token.empty() &&
        rex::ui::ParseVirtualKey(token) == event.virtual_key()) return true;
  }
  return false;
}

class KeyboardTaps final : public InputDriver, public rex::ui::WindowInputListener,
                           public rex::ui::WindowListener {
 public:
  KeyboardTaps(rex::ui::Window* window, std::function<bool()> active)
      : InputDriver(window, 0), attached_(window) {
    set_is_active_callback(std::move(active));
    if (attached_) {
      focused_ = attached_->HasFocus();
      attached_->AddInputListener(this, 0);
      attached_->AddListener(this);
    }
  }
  ~KeyboardTaps() override {
    if (attached_) attached_->app_context().CallInUIThreadSynchronous([this] { Detach(); });
  }
  X_STATUS Setup() override { return X_STATUS_SUCCESS; }
  void EnumerateDevices(std::vector<DeviceInfo>& devices) override {
    if (!Enabled()) { ClearEdges(); return; }
    DeviceInfo device;
    device.id = kDevice;
    device.name = "Keyboard button edges";
    device.synthetic = true;
    devices.push_back(std::move(device));
  }
  X_RESULT GetDeviceState(DeviceId id, X_INPUT_STATE* state) override {
    if (!Enabled() || id != kDevice) return X_ERROR_DEVICE_NOT_CONNECTED;
    // UI and guest code both poll input. Keep a short edge visible to both
    // rather than letting a UI poll consume the game's only copy.
    const auto now = NowMs();
    uint16_t pending = 0;
    for (unsigned bit = 0; bit < 16; ++bit)
      if (edge_until_[bit].load() > now) pending |= uint16_t(1u << bit);
    if (pending && REXCVAR_GET(psu_trace_input))
      REXLOG_INFO("PSU keyboard poll: buttons={:04X}, focused={}, active={}", pending, bool(focused_), is_active());
    if (state) {
      *state = {};
      state->packet_number = ++packet_;
      state->gamepad.buttons = focused_ && is_active() ? pending : 0;
    }
    return X_ERROR_SUCCESS;
  }
  X_RESULT GetDeviceCapabilities(DeviceId id, uint32_t, X_INPUT_CAPABILITIES* caps) override {
    if (!Enabled() || id != kDevice) return X_ERROR_DEVICE_NOT_CONNECTED;
    if (caps) {
      *caps = {};
      caps->type = 1;
      caps->sub_type = 1;
      caps->gamepad.buttons = 0xF3FF;
      caps->gamepad.left_trigger = caps->gamepad.right_trigger = 0xFF;
      caps->gamepad.thumb_lx = caps->gamepad.thumb_ly = -1;
      caps->gamepad.thumb_rx = caps->gamepad.thumb_ry = -1;
    }
    return X_ERROR_SUCCESS;
  }
  X_RESULT SetDeviceVibration(DeviceId id, X_INPUT_VIBRATION*) override {
    return Enabled() && id == kDevice ? X_ERROR_SUCCESS : X_ERROR_DEVICE_NOT_CONNECTED;
  }
  X_RESULT GetDeviceKeystroke(DeviceId id, uint32_t, X_INPUT_KEYSTROKE*) override {
    return Enabled() && id == kDevice ? X_ERROR_EMPTY : X_ERROR_DEVICE_NOT_CONNECTED;
  }
  void OnKeyDown(rex::ui::KeyEvent& event) override {
    if (REXCVAR_GET(psu_trace_input))
      REXLOG_INFO("PSU keyboard event: key={}, enabled={}, focused={}, active={}, repeat={}",
                  unsigned(event.virtual_key()), Enabled(), bool(focused_), is_active(), event.prev_state());
    if (!Enabled() || !focused_ || !is_active() || event.prev_state() ||
        event.is_super_pressed()) return;
    struct Binding { const char* name; uint16_t button; };
    static constexpr Binding bindings[] = {
        {"keybind_a", X_INPUT_GAMEPAD_A}, {"keybind_b", X_INPUT_GAMEPAD_B},
        {"keybind_x", X_INPUT_GAMEPAD_X}, {"keybind_y", X_INPUT_GAMEPAD_Y},
        {"keybind_start", X_INPUT_GAMEPAD_START}, {"keybind_back", X_INPUT_GAMEPAD_BACK},
        {"keybind_dpad_up", X_INPUT_GAMEPAD_DPAD_UP},
        {"keybind_dpad_down", X_INPUT_GAMEPAD_DPAD_DOWN},
        {"keybind_dpad_left", X_INPUT_GAMEPAD_DPAD_LEFT},
        {"keybind_dpad_right", X_INPUT_GAMEPAD_DPAD_RIGHT},
        {"keybind_left_shoulder", X_INPUT_GAMEPAD_LEFT_SHOULDER},
        {"keybind_right_shoulder", X_INPUT_GAMEPAD_RIGHT_SHOULDER},
        {"keybind_lstick_press", X_INPUT_GAMEPAD_LEFT_THUMB},
        {"keybind_rstick_press", X_INPUT_GAMEPAD_RIGHT_THUMB}};
    uint16_t buttons = 0;
    for (const auto& binding : bindings)
      if (Matches(rex::cvar::GetFlagByName(binding.name), event)) buttons |= binding.button;
    const auto until = NowMs() + 120;
    for (unsigned bit = 0; bit < 16; ++bit)
      if (buttons & (1u << bit)) edge_until_[bit].store(until);
  }
  void OnLostFocus(rex::ui::UISetupEvent&) override { focused_ = false; ClearEdges(); }
  void OnGotFocus(rex::ui::UISetupEvent&) override { focused_ = true; }
  void OnClosing(rex::ui::UIEvent&) override { Detach(); }
 private:
  static int64_t NowMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  void ClearEdges() { for (auto& edge : edge_until_) edge.store(0); }
  void Detach() {
    if (!attached_) return;
    attached_->RemoveInputListener(this);
    attached_->RemoveListener(this);
    attached_ = nullptr;
  }
  rex::ui::Window* attached_;
  std::atomic<bool> focused_{true};
  std::array<std::atomic<int64_t>, 16> edge_until_{};
  std::atomic<uint32_t> packet_{0};
};
}

std::unique_ptr<rex::input::InputDriver> MakePsuKeyboardTaps(
    rex::ui::Window* window, std::function<bool()> active) {
  return std::make_unique<KeyboardTaps>(window, std::move(active));
}

void InstallPsuKeyboardTaps(rex::system::IInputSystem* input, rex::ui::Window* window,
                                 std::function<bool()> active) {
  static_cast<rex::input::InputSystem*>(input)->AddDriver(
      MakePsuKeyboardTaps(window, std::move(active)));
}
