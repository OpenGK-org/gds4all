from dataclasses import dataclass, field
from enum import Enum
from xml.etree.ElementTree import Element
from utils import _get, get_message, get_lookup_table, get_from_collection

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
	status: int | None = None
	description: str | None = None

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
	description: str | None = None

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
	
@dataclass
class Module(GdsDataClass):
	system_id: str
	communication_setup: CommunicationSetup | None = None
	current_data: dict[int, CurrentDataNode] = field(default_factory=list)
	dtcs: list[Dtc] = field(default_factory=list)
	actuation_tests: list[ActuationTestNode] = field(default_factory=list)

			
	@staticmethod
	def _build_communication_setup(ecu: Element) -> CommunicationSetup | None:
		commset = ecu.findall('commset')[0]
		try:
			protocol = Protocol(int(_get(commset, 'protocolid'), 16))
		except ValueError as e:
			protocol = None

		# what the fuck is wrong with them?
		tester_id = _get(commset, 'testerid', cast_to=int, cast_args=(16,))#.lstrip().split(' ')[0]
		module_id = _get(commset, 'moduleid', cast_to=int, cast_args=(16,))#.lstrip().split(' ')[0]
		inferred_tester_id = None
		inferred_module_id = None
		
		if tester_id is None and protocol in (Protocol.CAN, Protocol.ISO_15765):
			for requestnode in commset.findall('startcomm/requestnode'):
				if (requestnode.attrib['request'] != ''):
					inferred_tester_id = int(requestnode.attrib['request'][1:4], 16)
					inferred_module_id = int(requestnode.attrib['response'][1:4], 16)
					break
		
		tx_id = tester_id if tester_id is not None else inferred_tester_id
		rx_id = module_id if tester_id is not None else inferred_module_id

		communication_setup = CommunicationSetup(
			tx_id=tx_id,
			rx_id=rx_id,
			vss_channel=_get(commset, 'vsschannel'),
			protocol=protocol,
			supported_functions=[
				SupportedFunction(
					index=_get(x, 'index'), 
				) for x in commset.findall('funcsupport')[0]
			]
		)

		return communication_setup

	@staticmethod
	def _build_current_data(ecu: Element) -> dict[int, CurrentDataNode]:
		current_data_nodes = {}
		for node in ecu.findall('currentdata/currentdatanode'):
			convrule = node.findall('convrule')[0]
			try:
				convtype = ConversionType(int(_get(convrule, 'convtype')))
			except (ValueError, TypeError) as e:
				print(e)
				continue

			if convtype == ConversionType.SIMPLE:
				add = float(_get(convrule, 'B', '0'))
				if add != 0:
					add = add * -1 # invert the value as GDS defs use subtraction
				conversion = ConversionSimple(
					factor=float(_get(convrule, 'A')), 
					add=add
				)
			elif convtype == ConversionType.SIMPLE_NO_ADD:
				conversion = ConversionSimple(
					factor=float(_get(convrule, 'A')),
				)
			elif convtype == ConversionType.BITFIELD_ENUM:
				values = get_lookup_table(_get(convrule, 'A'))
				if not values:
					print('Failed to load LUT')
					values = []

				conversion = ConversionBitfieldEnum(
					add=float(_get(convrule, 'B', '0')),
					shift=int(_get(convrule, 'C')),
					bitmask=int(_get(convrule, 'D'), 16),
					values=values
				)

			data_node = CurrentDataNode(
				index=_get(node, 'index'),
				name=get_from_collection(_get(node, 'index'), 'currentdata'),

				request_payload=_get(node, 'requestcode'),
				response_prefix=_get(node, 'response'),
				response_start_position=_get(node, 'startpos'),

				position=_get(node, 'realpos', int),
				size=int(_get(node, 'datasize')),
				data_type=_get(node, 'datatype'),
				min_value=int(_get(node, 'minvalue'), 16),
				max_value=int(_get(node, 'maxvalue'), 16),
				unit=get_message(_get(node, 'unit'), attribute='unit'),
				decimal_points=_get(node, 'floatrange', int),
				conversion=conversion
			)

			current_data_nodes[int(data_node.position)] = data_node
		return current_data_nodes

	@staticmethod
	def _build_actuation_tests(ecu: Element) -> list[ActuationTestNode]:
		actuation_tests = []
		for node in ecu.findall('actuationtest/actuationtestnode'):
			try:
				start_request = RequestNode.from_xml(node.findall('starttest')[0][0])
			except IndexError:
				start_request = None

			try:
				stop_request = RequestNode.from_xml(node.findall('stoptest')[0][0])
			except IndexError:
				stop_request = None

			try:
				end_request = RequestNode.from_xml(node.findall('endtest')[0][0])
			except IndexError:
				end_request = None

			test_node = ActuationTestNode(
				index=_get(node, 'index', int),
				name=get_from_collection(_get(node, 'index'), 'actuationtest'),

				start_condition=get_from_collection(_get(node, 'actuationtestcondition'), 'actuationtest'),
				stop_condition=get_from_collection(_get(node, 'stopcondition'), 'actuationtest'),
				request_condition=get_from_collection(_get(node, 'requestcondition'), 'actuationtest'),

				time=_get(node, 'actuationtesttime', int),
				request_time=_get(node, 'requesttime', int),

				start_request=start_request,
				stop_request=stop_request,
				end_request=end_request,
			)
			actuation_tests.append(test_node)
		return actuation_tests
			
	@classmethod
	def _from_xml(cls, ecu: Element) -> 'Module':
		dtc_section = ecu.find('dtc')
		dtcs = []
		if dtc_section is not None:
			dtcs = [Dtc.from_xml(x) for x in dtc_section.findall('dtcitemtree')]
		
		return cls(
			system_id=ecu.get('systemid'),
			dtcs=dtcs,
			communication_setup=cls._build_communication_setup(ecu),
			current_data=cls._build_current_data(ecu),
			actuation_tests=cls._build_actuation_tests(ecu),
		)
