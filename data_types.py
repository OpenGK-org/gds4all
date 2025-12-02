from dataclasses import dataclass, field
from enum import Enum
from xml.etree.ElementTree import Element

class ConversionType(Enum):
	SIMPLE = 1 # just multiply and add
	SIMPLE_NO_ADD = 2 # only difference between 1 seems to be the lack of add value?
	BITFIELD_ENUM = 3 # mask and shift, then match with string values from LUT

class Protocol(Enum):
	J1850_VPW = 0x01
	J1850_PWM = 0x02
	ISO_9141  = 0x03
	ISO_14230 = 0x04
	CAN       = 0x05
	ISO_15765 = 0x06
	SCI_A_TRANS = 0x08
	SCI_B_ENGINE = 0x09
	SCI_B_TRANS = 0x0A
	ISO_9141_2 = 0x10001
	BOSCH_BCM = 0x100015

@dataclass
class GdsDataClass:
	@classmethod
	def from_xml (self, element: Element):
		return self._from_xml(element)

@dataclass
class Conversion(GdsDataClass):
	type: ConversionType
	factor: float = 1
	add: float = 0

	def _equation_factor (self) -> str:
		if self.factor != 1:
			return '{:g}*'.format(self.factor)
		else:
			return ''

	def _equation_add (self) -> str:
		if self.add != 0:
			if self.add < 0:
				return '+{:g}'.format(abs(self.add))
			else:
				return '-{:g}'.format(self.add)
		else:
			return ''

	# tunerpro format
	def to_equation (self) -> str:
		return '{}X{}'.format(self._equation_factor(), self._equation_add())

	def __repr__ (self) -> str:
		return self.to_equation()

@dataclass
class ConversionSimple(Conversion):
	type: ConversionType = ConversionType.SIMPLE

	def __repr__ (self) -> str: # apparently __repr__ isnt inherited
		return self.to_equation()

@dataclass
class ConversionSimpleNoAdd(Conversion): 
	type: ConversionType = ConversionType.SIMPLE_NO_ADD

	def __repr__ (self) -> str:
		return self.to_equation()


@dataclass
class ConversionBitfieldEnum(Conversion):
	type: ConversionType = ConversionType.BITFIELD_ENUM
	shift: int = 0
	bitmask: int = 0x0
	values: list[str] = None

	def __repr__ (self) -> str:
		return '((X&{}) >> {}) -> [{}]'.format(
			hex(self.bitmask), 
			self.shift,
			'|'.join(self.values)
		)

@dataclass
class CurrentDataNode(GdsDataClass):
	# header: str ??
	index: int
	name: str

	request_payload: str # tbh this should probably be bytes
	response_prefix: str 
	response_start_position: int # this should be added to self.position if operating on raw response frames

	position: int
	
	size: int
	data_type: str # ??

	min_value: int
	max_value: int

	unit: str
	decimal_points: int

	# compid: str ??
	# freeze: ??
	# dtc: str ??

	conversion: Conversion

	def __repr__ (self) -> str:
		return 'CurrentDataNode(i={}, name=\'{}\', position={}, size={}, unit=\'{}\', conversion={})'.format(self.index, self.name, self.position, self.size, self.unit, self.conversion)

@dataclass
class RequestNode(GdsDataClass):
	request_payload: str
	response_prefix: str # XX - wildcard. @todo: convert this to hex and generate a mask. consider different length (it is a prefix after all)
	index: int | None = field(default=None, repr=False)

	@classmethod
	def _from_xml (self, node: Element):
		return self(
			request_payload=node.get('request'), 
			response_prefix=node.get('response'),
			index=node.get('index')
		)

@dataclass
class ActuationTestNode(GdsDataClass):
	# header: ??
	index: int
	name: str

	start_condition: str
	stop_condition: str
	request_condition: str
	time: int # seconds?
	request_time: int # ??? timeout?

	start_request: RequestNode
	stop_request: RequestNode
	end_request: RequestNode

	# compid: str ??

	def __repr__ (self) -> str:
		return('ActuationTestNode(i={}, name=\'{}\', start_condition=\'{}\', start_payload={})'.format(self.index, self.name, self.start_condition, self.start_request.request_payload))

@dataclass
class Dtc(GdsDataClass):
	header: str
	index: str
	mask: str # should be hex?
	freeze_index: str | None

	# commcode: str ?? 
	# compid: str ??

	@classmethod
	def _from_xml (self, node: Element):
		return self(
			index=node.get('index'),
			header=node.get('header'),
			mask=node.get('mask'),
			freeze_index=node.findall('freezeindex')[0].get('index') # @todo?
		)

@dataclass
class DtcFunction(GdsDataClass):
	requests: list[RequestNode]
	dtcs: list[Dtc]

@dataclass
class SupportedFunction(GdsDataClass):
	index: int
	description: str

@dataclass
class CommunicationSetup(GdsDataClass):
	tx_id: int | None
	rx_id: int # / module id
	vss_channel: str # ???
	protocol: Protocol

	supported_functions: list[SupportedFunction]

	# @TODO

	def __repr__ (self) -> str:
		return 'CommunicationSetup(tx_id={}, rx_id={}, protocol={})'.format(hex(self.tx_id) if self.tx_id else 'None', hex(self.rx_id) if self.rx_id else 'None', self.protocol.name)