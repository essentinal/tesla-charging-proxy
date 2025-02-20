# Tesla Charging Proxy Integration for Home Assistant

This custom integration for Home Assistant provides proxy entities for controlling Tesla charging settings, specifically the maximum charging current and charging switch.  It allows buffering commands and avoiding duplicate requests, ensuring more reliable communication with the Tesla vehicle.

## Features

*   **Proxy Entities:** Creates proxy `number` and `switch` entities that mirror the state of the original Tesla charging entities.
*   **Command Buffering:** Buffers commands to avoid sending frequent or duplicate requests to the Tesla vehicle.
*   **Loop Prevention:** Prevents feedback loops between the proxy and the original entities.
*   **State Restoration:** Restores the state of the proxy entities after a Home Assistant restart.
*   **Device Association:** Correctly associates the proxy entities with the original Tesla device in Home Assistant.

## Installation

1.  **Copy the `tesla_charging_proxy` directory:** Copy the entire `tesla_charging_proxy` directory to your Home Assistant's `custom_components` directory.  If the `custom_components` directory doesn't exist, create it in your Home Assistant configuration directory (where your `configuration.yaml` is located).

    The final path should look like this: `/<config_dir>/custom_components/tesla_charging_proxy/`

2.  **Restart Home Assistant:** Restart your Home Assistant instance to load the custom integration.

3.  **Configure the Integration:**

    *   Go to **Configuration** -> **Integrations** in your Home Assistant UI.
    *   Click the "+" button to add a new integration.
    *   Search for "Tesla Charging Proxy" and select it.
    *   Follow the configuration steps. You'll need to provide the entity IDs of the original Tesla charging entities you want to proxy (e.g., `number.blacky_maximaler_ac_ladestrom`, `switch.blacky_charging`).

## Configuration

The integration is configured through the Home Assistant UI.  You will be prompted to enter the following information:

*   **Name:**  A name for the proxy (e.g., "Blacky", "Tessy").  This will be used to create the names of the proxy entities (e.g., `number.blacky_charging_current_proxy`, `switch.blacky_charging_switch_proxy`).
*   **Maximum Charging Current Entity:** The entity ID of the Tesla's maximum charging current number entity (e.g., `number.tessy_maximaler_ac_ladestrom`).
*   **Charging Switch Entity:** The entity ID of the Tesla's charging switch entity (e.g., `switch.tessy_charging`).

**Example:**

If you have two Teslas named "Blacky" and "Tessy," you would configure two instances of this integration, providing the corresponding entity IDs for each vehicle.

## Entities Created

This integration creates the following entities for each configured Tesla vehicle:

*   **Number Entity (`number.xxxx_charging_current_proxy`):**  A number entity that allows you to set the maximum charging current for the Tesla. It buffers commands and prevents duplicate requests.
    *   Minimum value: 1 Ampere
    *   Maximum value: 16 Amperes
    *   Step: 1 Ampere
*   **Switch Entity (`switch.xxxx_charging_switch_proxy`):** A switch entity that allows you to turn the Tesla charging on or off. It buffers commands and prevents duplicate requests.

Replace `xxxx` with the name you provided during configuration (e.g., "blacky", "tessy").

## How it Works

The integration creates proxy entities that mirror the state of the original Tesla charging entities. When you interact with the proxy entities (e.g., change the charging current or toggle the charging switch), the integration:

1.  **Buffers the command:**  The desired state is stored, but the command is not immediately sent to the Tesla.
2.  **Checks for duplicates:** The integration verifies that the new command is different from the previous one to avoid sending duplicate requests.
3.  **Sends the command (if necessary):** The integration sends the command to the original Tesla charging entity, updating the charging settings on the vehicle.

This approach helps to reduce the number of API calls to the Tesla and prevent potential issues caused by sending too many requests in a short period.

## Troubleshooting

*   **Entities not appearing:**
    *   Ensure the integration is properly installed in the `custom_components` directory.
    *   Restart Home Assistant.
    *   Verify the entity IDs entered during configuration are correct.
    *   Check the Home Assistant logs for any error messages related to the integration.
*   **Proxy not updating:**
    *   Check the Home Assistant logs for errors.
    *   Ensure the original Tesla entities are functioning correctly.
    *   Verify that the Tesla integration is properly configured and authenticated.

## Known Issues

*   (None currently)

## Contributing

Contributions are welcome!  Please submit pull requests with bug fixes, new features, or improvements to the documentation.

## License

This integration is released under the [GPL 3](LICENSE) license.
