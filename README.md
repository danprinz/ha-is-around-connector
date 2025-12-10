# Is Around Connector

This integration connects to the Is Around application to retrieve observances and print PDFs.

**Note:** This integration depends on `ipp_printer_service`. Please install that integration first.

## Installation

### HACS

1. Open HACS.
2. Go to "Integrations".
3. Click the 3 dots in the top right corner and select "Custom repositories".
4. Add the URL of this repository.
5. Select "Integration" as the category.
6. Click "Add".
7. Find "Is Around Connector" in the list and install it.
8. Restart Home Assistant.

### Manual

1. Copy the `custom_components/is_around_connector` folder to your `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

This integration supports config flow. Go to Settings -> Devices & Services -> Add Integration and search for "Is Around Connector".
