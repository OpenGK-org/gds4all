import xml.etree.ElementTree as ET
import sys, glob, os, textwrap
from data_types import Conversion, ConversionSimple, ConversionBitfieldEnum, ConversionType, CurrentDataNode, RequestNode, ActuationTestNode, Dtc, DtcFunction, SupportedFunction, Protocol, CommunicationSetup

# used for debugging. set sys.argv to, say, 26, 3, 1. 
# a 2006 2.0 tiburon will be selected: vehicle 26, year 3, variant 1
prefilled_interactive_selects = []

TERMINAL_WIDTH = os.get_terminal_size().columns

messages = {}
collections = {}

def _get (xml, param: str, default = None, cast_to = None, cast_args: tuple = None) -> str | None:
	value = xml.get(param, default)
	
	if value == '':
		return default

	if cast_to:
		try:
			value = cast_to(value, *cast_args)
		except (TypeError, ValueError) as e:
			value = None
	
	return value

def _print (*args, indent: int = 0, **kwargs):
	return print(' '*indent, *args, **kwargs)
	
def interactive_select (table, prompt):
	if (len(prefilled_interactive_selects) > 0):
		index = int(prefilled_interactive_selects.pop(0))
		print('Prefilled: {}'.format(index))
		return table[index]

	try:
		return table[int(input(prompt))]
	except (KeyError, IndexError, ValueError):
		print('Invalid choice! Try again')
		return interactive_select(table, prompt)

def load_vehicles ():
	tree = ET.parse('decrypted_xef/vehiclesdata_HME.xml')
	root = tree.getroot()
	vehicles = []

	for child in root:
		vehicles.append(child)

	return vehicles

def load_messages (dataset: str):
	tree = ET.parse(dataset).getroot()
	for keyvalue in tree:
		if keyvalue.attrib['attr'] not in messages:
			messages[keyvalue.attrib['attr']] = {}
		messages[keyvalue.attrib['attr']][keyvalue.attrib['key']] = keyvalue.attrib['desc']

def load_collections (dataset: str):
	tree = ET.parse(dataset).getroot()

	for collection in tree:
		collections[collection.tag] = {}
		for keyvalue in collection:
			collections[collection.tag][keyvalue.attrib['key']] = keyvalue.attrib['desc']

def load_ecu (ecu_code: str):
	print('Loading ECU code: {}'.format(ecu_code))
	patterns = {'Exact Match': 'decrypted_xef/{}.xml', 
			   'Largest DGN Suffix File': 'decrypted_xef/{}[DGN]0.xml', 
			   'Wildcard': 'decrypted_xef/{}*.xml'}
	for name, pattern in patterns.items():
		files = glob.glob(pattern.format(ecu_code))
		if len(files) == 0:
			continue
		elif len(files) == 1:
			file = files[0]
		else:
			file = max(files, key=lambda file: os.stat(file).st_size)
		try:
			tree = ET.parse(file)
		except ET.ParseError:
			print('File {} was found but failed to parse'.format(file))
			continue
		root = tree.getroot()
		if len(root) == 0:
			print('File {} was found but apparently contains no root'.format(file))
		else:
			print('Loaded ECU using pattern: {}'.format(name))
			return root
	return None

def get_message (key: int, attribute: str = None):
	try:
		return messages[attribute][key]
	except KeyError:
		return ''

def get_from_collection (key: str, collection_name: str = 'currentdata'):
	try:
		return collections[collection_name][key]
	except KeyError:
		return ''

def get_lookup_table (identifier: int) -> list|None:
	lut_filenames = [f'Lut/{identifier}.lut', f'Lut/{identifier}.LUT'] # consistency [cool]
	values = []

	for lut_filename in lut_filenames:
		try:
			with open(lut_filename, 'r') as f:
				for value in f.readlines():
					values.append(value.lstrip().rstrip())
			return values
		except FileNotFoundError:
			pass
	return None


def handle_step (bus, step):
	print('Step #{}'.format(step.attrib['stepno']))
	print(get_message(step.attrib['stepdesc'], attribute='stepdesc'))

	message = step.findall('message')[0]
	if (message.attrib['messageindex'] != '0'):
		print(get_message(message.attrib['messageindex'], attribute='messageindex'))

	keystrings = step.findall('keystring')

	print('\n')
	if (keystrings[0].attrib['type'] != '0'):
		for key, keystring in enumerate(keystrings):
			print('[{}] {}'.format(key, keystring.attrib['filename']))
		keystring = interactive_select(keystrings, '=========\nSelect: ')

		if 'jumpstep' in keystring.attrib:
			return int(keystring.attrib['jumpstep'])

	for request in message.findall('request'):
		for response in request:
			print('    Expected response format: {}\n'.format(response.attrib['responsevalue']))
			print('    We\'re looking for some data with size {}, starting at offset {}'.format(response.attrib['datasize'], response.attrib['startposition']))

			for comcode in response.findall('comcode'):
				operation_name = 'equals to' if comcode.attrib['compare'] == '1' else 'does not equal' 
				print('    - If this data {} {}, then we jump to step {}'.format(operation_name, comcode.attrib['code'], comcode.attrib['jumpstep']))

	return False

def main ():
	print('loading messages..')
	load_messages('decrypted_xef/add-ENG.xml')
	load_messages('decrypted_xef/keyvalue.xml')
	load_messages('decrypted_xef/keyvalueUnit.xml') 

	print('loading collections..')
	load_collections('decrypted_xef/dtc-ENG.xml')

	if not os.path.isdir('Lut'):
		print('[!] Lookup table files not found, enum values won\'t be extracted.')
		print('You can find them in the Lut directory in main GDS dir')

	print('loading vehicles..')

	vehicles = load_vehicles()

	for key, vehicle in enumerate(vehicles):
		print('[{}] - {}'.format(key, vehicle.get('modeldesc')))

	vehicle = interactive_select(vehicles, 'Select vehicle: ')
	print('selected vehicle: {}'.format(vehicle.get('modeldesc')))

	# manufacturer, lang, vehicle type, model vin
	vehicle_years = vehicle[0][0][0][0][0]
	
	for key, vehicle_year in enumerate(vehicle_years):
		print('[{}] - {}'.format(key, vehicle_year.get('modelyr')))

	vehicle_variants = interactive_select(vehicle_years, 'Select year: ')

	for key, variant in enumerate(vehicle_variants):
		print('[{}] - {}'.format(key, variant.get('enginedesc')))

	vehicle_systems = interactive_select(vehicle_variants, 'Select engine type: ')

	for key, system in enumerate(vehicle_systems):
		print('\n[{}] - {}'.format(key, system.get('sysitemdesc')))
		print('    {}'.format('/'.join([subsystem.get('syssubitemdesc') for subsystem in system])))

	vehicle_system = interactive_select(vehicle_systems, 'Select system: ')
	
	if (len(vehicle_system) > 1):
		for key, subsystem in enumerate(vehicle_system):
			print('[{}] {}'.format(key, subsystem.get('syssubitemdesc')))
		vehicle_system = interactive_select(vehicle_system, 'Select subsystem: ')
	else:
		vehicle_system = vehicle_system[0]

	print('\n\n\nSelected system: {}'.format(vehicle_system.get('syssubitemdesc')))
	if len(vehicle_system) > 1:
		print('There is more than one ECU assigned to this subsystem: {}'.format(', '.join([ecu.get('ecucode') for ecu in vehicle_system])))

	for ecu_node in vehicle_system:
		ecu_code = ecu_node.attrib['ecucode']
		ecu = load_ecu(ecu_code)

		if ecu == None:
			print('[!] Failed to load ECU definition: {}'.format(ecu_code))
			continue

		print('\nLoaded ECU: {}, definition last modified: {}'.format(ecu.get('systemid'), ecu.get('date')))

		print('=== Communication ===')

		commset = ecu.findall('commset')[0]
		print('    Protocol used: {}'.format(get_message(commset.get('protocolid'), 'protocolid')))
		try:
			protocol = Protocol(int(_get(commset, 'protocolid'), 16))
		except ValueError as e:
			protocol = None
			print(e)
			continue


		# what the fuck is wrong with them?
		tester_id = _get(commset, 'testerid', cast_to=int, cast_args=(16,))#.lstrip().split(' ')[0]
		module_id = _get(commset, 'moduleid', cast_to=int, cast_args=(16,))#.lstrip().split(' ')[0]

		#tester_id = int(tester_id, 16)#None if len(tester_id) == 0 else int(tester_id, 16)
		#module_id = int(module_id, 16)#None if len(module_id) == 0 else int(module_id, 16)


		communication_setup = CommunicationSetup(
			tx_id=tester_id,
			rx_id=module_id,
			vss_channel=_get(commset, 'vsschannel'),
			protocol=protocol,
			supported_functions=[
				SupportedFunction(
					index=_get(x, 'index'), 
					description=get_message(_get(x, 'index'), attribute='index')
				) for x in commset.findall('funcsupport')[0]
			]
		)
		_print('{}'.format(communication_setup), indent=4)

		for requestnode in commset.findall('startcomm/requestnode'):
			if (requestnode.attrib['request'] != ''):
				_print('Connect payload: {}'.format(requestnode.attrib['request']), indent=4)
				_print('Expected response: {}'.format(requestnode.attrib['response']), indent=4)

		print('\n=== This ECU supports following functions: ===')
		for function_declaration in communication_setup.supported_functions:
			_print('- {} ({})'.format(function_declaration.description, function_declaration.index), indent=4)

		_print('=== Current data function ===', indent=4)
		current_data_nodes = {}
		for node in ecu.findall('currentdata/currentdatanode'):
			convrule = node.findall('convrule')[0]
			try:
				convtype = ConversionType(int(_get(convrule, 'convtype')))
			except ValueError as e:
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
					_print('Failed to load LUT', indent=8)
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


		for data_node in [v for k, v in sorted(current_data_nodes.items())]:
			_print('- {}: ({})'.format(data_node.name, data_node.index), indent=8)
			_print('Payload: {}'.format(data_node.request_payload), indent=12)
			_print('Response format: {}'.format(data_node.response_prefix), indent=12)
			

			
			if (_get(node, 'unit', 0, int) != 0):
				_print('Unit: {} ({})'.format(data_node.unit, node.get('unit')), indent=12)
			_print('Position: {} Size: {}'.format(data_node.position, data_node.size), indent=12)
			_print('Precision: {}'.format(data_node.decimal_points), indent=12)
			_print('Conversion: {} ({})'.format(data_node.conversion, convtype), indent=12)

			print()

		_print('=== Actuation test function ===', indent=4)
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
			_print(str(test_node), indent=8)
			_print('Start payload: {}'.format(test_node.start_request.request_payload), indent=12)

		print('\n    === DTCs: ===')
		for node in ecu.findall('dtc'):
			dtc_func = DtcFunction(
				requests=[
					RequestNode.from_xml(x) for x in node.findall('requestcodetree')[0].findall('requestnode')
				],
				dtcs=[
					Dtc.from_xml(x) for x in node.findall('dtcitemtree')
				]
			)

			_print('Request: {}'.format(dtc_func.requests[0]), indent=8)
			for dtc in dtc_func.dtcs:
				_print('{}'.format(str(dtc)), indent=8)


		print('\n    === "addfunction" functions: ===')
		addfunction_functions = ecu.findall('addfunction')
		for key, node in enumerate(addfunction_functions):
			_print('[{}] {}'.format(key, get_message(node.get('fuctionindex'), attribute='index')), indent=8)
			_print('{}'.format(get_message(node.get('fuctiondesc'), attribute='fuctiondesc')), indent=12)
			_print('Steps:', indent=12)
			for step in sorted(node.findall('step'), key=lambda s: int(_get(s, 'stepno'))):
				_print('#{} {}'.format(_get(step, 'stepno'), get_message(_get(step, 'stepdesc'), attribute='stepdesc')), indent=16)
				message = step.findall('message')[0]
				if (message.get('messageindex') != '0'):
					message_text = get_message(message.get('messageindex'), attribute='messageindex')
					message_lines = message_text.split('\\n')
					for i, line in enumerate(message_lines):
						try:
							if line == '' and message_lines[i+1] == '':
								continue
						except IndexError:
							pass

						line = line.strip().replace('\n', '')

						# make sure no line is crossing the indent, i hate that
						for line in textwrap.wrap(line, width=(TERMINAL_WIDTH-20)):
							_print('{}'.format(line), indent=20)
					

		_stephandlingmethods = '''continue # ACHTUNG!
		selected_function = interactive_select(addfunction_functions, 'Select function: ')

		print('\n\n\n==========')
		print(get_message(selected_function.attrib['fuctiondesc'], attribute='fuctiondesc'))

		function_steps = sorted(selected_function.findall('step'), key=lambda s: int(s.attrib['stepno']))
		next_step_no = handle_step(bus, function_steps[0])
		while next_step_no:
			try:
				next_step = function_steps[next_step_no-1]
				next_step_no = handle_step(bus, next_step)
				if (next_step_no == 0):
					break
			except (IndexError, KeyError):
				break'''

	if (len(vehicle_system) > 1):
		print('[!] Be advised: more than 1 ECU definition was processed and displayed')

if __name__ == '__main__':
	if len(sys.argv) > 1:
		prefilled_interactive_selects = sys.argv[1:]
	main()
