import 'package:flutter/material.dart';

void resetPagedScroll(ScrollController controller) {
  if (controller.hasClients) {
    controller.jumpTo(0);
    return;
  }
  WidgetsBinding.instance.addPostFrameCallback((_) {
    if (!controller.hasClients) return;
    controller.jumpTo(0);
  });
}
