#pragma once
#include <functional>
#include <memory>
namespace rex::system { class IInputSystem; }
namespace rex::ui { class Window; }
namespace rex::input { class InputDriver; }
std::unique_ptr<rex::input::InputDriver> MakePsuKeyboardTaps(
    rex::ui::Window* window, std::function<bool()> active);
void InstallPsuKeyboardTaps(rex::system::IInputSystem* input,
                                 rex::ui::Window* window,
                                 std::function<bool()> active);
