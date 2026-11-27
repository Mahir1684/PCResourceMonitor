export TARGET = iphone:clang:9.3:9.0
export ARCHS = armv7
THEOS ?= $(HOME)/theos

include $(THEOS)/makefiles/common.mk

APPLICATION_NAME = PCResourceMonitor

PCResourceMonitor_FILES = \
    src/main.m \
    src/AppDelegate.m \
    src/Controllers/PRMDashboardViewController.m \
    src/Models/PRMTelemetrySnapshot.m \
    src/Services/PRMTelemetryClient.m \
    src/Views/PRMProgressBar.m \
    src/Views/PRMTelemetryRow.m \
    src/Views/PRMCardView.m \
    src/Views/PRMStatusHeaderView.m

PCResourceMonitor_FRAMEWORKS = UIKit Foundation CoreGraphics QuartzCore
PCResourceMonitor_CFLAGS = -fobjc-arc -Wall -Wextra -O2 -Isrc
PCResourceMonitor_CODESIGN_FLAGS = -Sentitlements.xml
PCResourceMonitor_RESOURCE_FILES = Info.plist
PCResourceMonitor_RESOURCE_DIRS = Resources

include $(THEOS_MAKE_PATH)/application.mk

after-all::
	@echo "Packaging IPA..."
	@rm -rf $(THEOS_OBJ_DIR)/Payload
	@mkdir -p $(THEOS_OBJ_DIR)/Payload
	@cp -r $(THEOS_OBJ_DIR)/$(APPLICATION_NAME).app $(THEOS_OBJ_DIR)/Payload/
	@cd $(THEOS_OBJ_DIR) && zip -q -r9 $(APPLICATION_NAME).ipa Payload/
	@rm -rf $(THEOS_OBJ_DIR)/Payload
	@echo "IPA successfully created at $(THEOS_OBJ_DIR)/$(APPLICATION_NAME).ipa"
