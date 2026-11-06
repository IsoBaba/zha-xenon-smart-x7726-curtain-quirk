"""ZHA quirk for the Xenon Smart X7726 curtain motor (TS0601 / _TZE284_hbjwgkdh)."""

from typing import Final

import zigpy.types as t
from zigpy.zcl import foundation
from zigpy.zcl.clusters.closures import WindowCovering

try:
    from zhaquirks.builder import QuirkBuilder
except ImportError:  # older zha-quirks versions
    from zigpy.quirks.v2 import QuirkBuilder

from zhaquirks.tuya import (
    TUYA_MCU_COMMAND,
    TuyaLocalCluster,
    TuyaPowerConfigurationClusterOther,
)
from zhaquirks.tuya.mcu import DPToAttributeMapping, TuyaClusterData, TuyaMCUCluster


class TuyaCoverCommand(t.enum8):
    """Tuya DP1 (control) values, verified from device logs."""

    OPEN = 0x00
    STOP = 0x01
    CLOSE = 0x02


class MotorDirection(t.enum8):
    """DP101: motor rotation direction (0 = open turns clockwise, 1 = counter-clockwise)."""

    Normal = 0x00
    Reversed = 0x01


class CurtainCoveringCluster(TuyaLocalCluster, WindowCovering):
    """WindowCovering cluster exposed to HA; translates commands to Tuya MCU datapoints."""

    _CONSTANT_ATTRIBUTES = {
        WindowCovering.AttributeDefs.window_covering_type.id: (
            WindowCovering.WindowCoveringType.Drapery
        ),
    }

    async def command(
        self,
        command_id,
        *args,
        manufacturer=None,
        expect_reply=True,
        tsn=None,
        **kwargs,
    ):
        """Translate ZCL commands into Tuya DP commands."""
        attr = None
        value = None

        if command_id == WindowCovering.ServerCommandDefs.up_open.id:
            attr, value = "control", TuyaCoverCommand.OPEN
        elif command_id == WindowCovering.ServerCommandDefs.down_close.id:
            attr, value = "control", TuyaCoverCommand.CLOSE
        elif command_id == WindowCovering.ServerCommandDefs.stop.id:
            attr, value = "control", TuyaCoverCommand.STOP
        elif command_id == WindowCovering.ServerCommandDefs.go_to_lift_percentage.id:
            # Motor: 0 = open, 100 = closed. Same direction as ZCL, no conversion needed.
            attr, value = "percent_control", args[0]

        if attr is None:
            self.warning("Unsupported WindowCovering command: 0x%02x", command_id)
            return foundation.GENERAL_COMMANDS[
                foundation.GeneralCommand.Default_Response
            ].schema(
                command_id=command_id,
                status=foundation.Status.UNSUP_CLUSTER_COMMAND,
            )

        self.endpoint.device.command_bus.listener_event(
            TUYA_MCU_COMMAND,
            TuyaClusterData(
                endpoint_id=self.endpoint.endpoint_id,
                cluster_name=TuyaMCUCluster.ep_attribute,
                cluster_attr=attr,
                attr_value=value,
                expect_reply=expect_reply,
                manufacturer=manufacturer,
            ),
        )
        return foundation.GENERAL_COMMANDS[
            foundation.GeneralCommand.Default_Response
        ].schema(command_id=command_id, status=foundation.Status.SUCCESS)


class CurtainMCUCluster(TuyaMCUCluster):
    """0xEF00 cluster: DP <-> attribute mapping."""

    class AttributeDefs(TuyaMCUCluster.AttributeDefs):
        """Virtual attributes (one per datapoint)."""

        control: Final = foundation.ZCLAttributeDef(
            id=0xEF01, type=t.enum8, is_manufacturer_specific=True
        )
        percent_control: Final = foundation.ZCLAttributeDef(
            id=0xEF02, type=t.uint32_t, is_manufacturer_specific=True
        )
        dp_101: Final = foundation.ZCLAttributeDef(
            id=0xEF65, type=MotorDirection, is_manufacturer_specific=True
        )
        dp_102: Final = foundation.ZCLAttributeDef(
            id=0xEF66, type=t.enum8, is_manufacturer_specific=True
        )
        dp_103: Final = foundation.ZCLAttributeDef(
            id=0xEF67, type=t.uint32_t, is_manufacturer_specific=True
        )
        dp_104: Final = foundation.ZCLAttributeDef(
            id=0xEF68, type=t.uint32_t, is_manufacturer_specific=True
        )
        dp_105: Final = foundation.ZCLAttributeDef(
            id=0xEF69, type=t.uint32_t, is_manufacturer_specific=True
        )
        dp_106: Final = foundation.ZCLAttributeDef(
            id=0xEF6A, type=t.uint32_t, is_manufacturer_specific=True
        )

    dp_to_attribute: dict[int, DPToAttributeMapping] = {
        1: DPToAttributeMapping(
            TuyaMCUCluster.ep_attribute,
            "control",
            dp_converter=lambda x: TuyaCoverCommand(x),
        ),
        2: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "percent_control"),
        3: DPToAttributeMapping(
            CurtainCoveringCluster.ep_attribute,
            "current_position_lift_percentage",
        ),
        13: DPToAttributeMapping(
            TuyaPowerConfigurationClusterOther.ep_attribute,
            "battery_percentage_remaining",
            converter=lambda x: x * 2,
        ),
        101: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "dp_101"),
        102: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "dp_102"),
        103: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "dp_103"),
        104: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "dp_104"),
        105: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "dp_105"),
        106: DPToAttributeMapping(TuyaMCUCluster.ep_attribute, "dp_106"),
    }

    data_point_handlers = {
        1: "_dp_2_attr_update",
        2: "_dp_2_attr_update",
        3: "_dp_2_attr_update",
        13: "_dp_2_attr_update",
        101: "_dp_2_attr_update",
        102: "_dp_2_attr_update",
        103: "_dp_2_attr_update",
        104: "_dp_2_attr_update",
        105: "_dp_2_attr_update",
        106: "_dp_2_attr_update",
    }


(
    QuirkBuilder("_TZE284_hbjwgkdh", "TS0601")
    .replaces(CurtainMCUCluster)
    .adds(CurtainCoveringCluster)
    .adds(TuyaPowerConfigurationClusterOther)
    .enum(
        attribute_name="dp_101",
        enum_class=MotorDirection,
        cluster_id=CurtainMCUCluster.cluster_id,
        translation_key="motor_direction",
        fallback_name="Motor direction",
    )
    .write_attr_button(
        attribute_name="dp_102",
        attribute_value=0,
        cluster_id=CurtainMCUCluster.cluster_id,
        unique_id_suffix="limit_learn_start",
        translation_key="limit_learn_start",
        fallback_name="Limit 1/2: Save closed position and start opening",
    )
    .write_attr_button(
        attribute_name="dp_102",
        attribute_value=1,
        cluster_id=CurtainMCUCluster.cluster_id,
        unique_id_suffix="limit_learn_stop",
        translation_key="limit_learn_stop",
        fallback_name="Limit 2/2: Save open position",
    )
    .skip_configuration()
    .add_to_registry()
)
