# Top-level Makefile: run cmake in build/ and delegate to it.
# Use: make [all], make install, make test

BUILD_DIR = build

all:
	@mkdir -p $(BUILD_DIR) && cd $(BUILD_DIR) && cmake .. && $(MAKE)

install: all
	cd $(BUILD_DIR) && $(MAKE) install

test: all
	cd $(BUILD_DIR) && $(MAKE) test

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all install test clean
