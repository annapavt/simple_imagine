import os.path
import logging
import numpy as np
import gzip
import common
import h5py

logger = logging.getLogger(__name__)


class Scan:
    """ scan master class that handles all volume scans operations from
          loading, handeling masks and more sophisticated ( such as brain and
          normalization )"""

    def __init__(self, volume=None):
        self.uid = ''
        self.directory = ''
        self.compressed_volume_directory = None
        self.volume = volume or []  # the CT scan volume
        self.path = []
        self.name = []  # patient name or number
        self.date = []  # scan date
        self.time = []
        self.modality = []
        self.defWindow = []  # default viewing window
        self.masks = []
        self.extradata = []  # costum saved user data
        self.metadata = []
        self.roiTexts = []
        self.size = None
        self.volume_compressed = False
        # self.__init__()
        # Read data

    @classmethod
    def fromID(cls, uid, scanfolder='', read_volume=True, prefer_compressed_volume=True,
               compressed_volumes_dir=None):
        scan = cls()
        if len(scanfolder) == 0:
            scanfolder = common.getTMpath('CTscans')

        filename = common.string2hash(uid)

        filename = os.path.join(scanfolder, filename + '.mat')

        if not os.path.isfile(filename):
            raise IOError("Could not find file" + filename)

        rawScan = h5py.File(filename)

        if 'volume' not in rawScan:
            raise IOError("Invalid scan in file " + filename)

        scan.uid = uid
        scan.directory = scanfolder
        scan.compressed_volume_directory = compressed_volumes_dir or scanfolder
        scan.name = rawScan['name'].value.tostring().decode('utf-16')
        scan.defWindow = rawScan['defWindow'].value
        scan.normWindow = rawScan['defWindow'].value + rawScan['matlabWindowShift'].value
        scan.metadata = _read_metadata(rawScan, rawScan['metadata'])
        scan.body_part = _get_body_part(rawScan)
        try:
            scan.plane = _get_plane(rawScan)
        except Exception as e:
            if scan.body_part == 'brain':
                # We can assume the scan is axial
                logger.warning('uid %s: %s - assuming Axial', uid, str(e))
                scan.plane = 'axial'
            else:
                raise e

        scan.image_orientation = scan.metadata['ImageOrientationPatient'].tolist()

        if 'size' not in rawScan:
            logger.warning('CTscan is missing the "size" field - computing from volume')
            # Volume shape is read as (slice, columns, rows). We want to reorder it to (slice, rows, columns)
            scan.size = rawScan['volume'].shape
            scan.size = [scan.size[0], scan.size[2], scan.size[1]]
        else:
            # The size is read as (rows, columns, slices). To match the volume, we change it to (slices, rows, colums)
            scan.size = rawScan['size'].value.flatten().astype(np.uint16)
            scan.size = [scan.size[2], scan.size[0], scan.size[1]]

        try:
            scan.image_positions = _read_image_positions(rawScan, scan.size[0], scan.plane)
        except Exception as e:
            logger.warning('uid %s: %s', uid, str(e))
            scan.image_positions = []

        if scan.body_part == 'brain':
            # Brain scans may require down-sampling
            scan.is_simulated_short = _is_simulated_short_scan(rawScan)
        else:
            scan.is_simulated_short = False


        if read_volume:
            scan.volume = None
            compressed_volume_file = os.path.join(scan.compressed_volume_directory, common.string2hash(uid) + '.dat.gz')
            if prefer_compressed_volume and os.path.isfile(compressed_volume_file):
                try:
                    with open(compressed_volume_file, 'rb') as f:
                        scan.volume = f.read()
                    scan.volume_compressed = True
                except Exception:
                    logger.exception('uid %s: Error reading compressed volume', uid)

            if not scan.volume:
                scan.volume = rawScan['volume']
                # Volume shape is read as (slice, columns, rows). We want to reorder it to (slice, rows, columns)
                scan.volume = np.transpose(scan.volume, (0, 2, 1))
                scan.volume_compressed = False

        return scan

    def getMask(self, idx):
        if idx < len(self.masks):
            return self.masks[idx]
        return []

    def getActiveMasks(self):
        activeMasks = []
        for i in range(len(self.masks)):
            if self.masks[i] != []:
                activeMasks.append(i)
        return activeMasks

    def is_color_image(self):
        photometric_interpretation = self.metadata['PhotometricInterpretation'].upper()
        return (photometric_interpretation in ['RGB', 'PALETTE COLOR', 'YBR_FULL', 'YBR_FULL_422', 'YBR_PARTIAL_422',
                                               'YBR_PARTIAL_420', 'YBR_RCT', 'YBR_ICT'])

    def store_compressed_volume(self):
        if len(self.volume) == 0 or self.volume_compressed:
            return

        volume = self.volume
        if self.body_part == 'brain' and self.is_simulated_short:
            volume = volume[::4]

        compressed_volume_file = os.path.join(self.compressed_volume_directory,
                                              common.string2hash(self.uid) + '.dat.gz')
        with open(compressed_volume_file, 'wb') as f:
            gzip_file = gzip.GzipFile(mode='wb', fileobj=f, compresslevel=9)
            gzip_file.write(volume.tobytes())
            gzip_file.close()


def _read_metadata(rawScan, rawMetadata):
    metadata = {}
    metadataKeys = rawMetadata.keys()
    extraData = rawScan['extraData']
    metadata['PhotometricInterpretation'] = rawMetadata['PhotometricInterpretation'].value.tostring().decode('utf-16')

    if 'AN' in extraData and extraData['AN']:
        metadata['AccessionNumber'] = _get_hdf5_string(extraData['AN'])
    elif 'AccessionNumber' in metadataKeys:
        metadata['AccessionNumber'] = _get_hdf5_string(rawMetadata['AccessionNumber'])

    if 'StudyInstanceUID' in metadataKeys:
        metadata['StudyInstanceUID'] = _get_hdf5_string(rawMetadata['StudyInstanceUID'])

    if 'RescaleSlope' in metadataKeys:
        metadata['RescaleSlope'] = np.asscalar(rawMetadata['RescaleSlope'].value)

    if 'RescaleIntercept' in metadataKeys:
        metadata['RescaleIntercept'] = np.asscalar(rawMetadata['RescaleIntercept'].value)

    if 'PixelSpacing' in metadataKeys:
        metadata['PixelSpacing'] = rawMetadata['PixelSpacing'].value[0]

    if 'SliceThickness' in metadataKeys:
        metadata['SliceThickness'] = np.asscalar(rawMetadata['SliceThickness'].value)

    if 'SpacingBetweenSlices' in metadataKeys:
        metadata['SpacingBetweenSlices'] = np.asscalar(rawMetadata['SpacingBetweenSlices'].value)

    if 'ImageOrientationPatient' in metadataKeys:
        metadata['ImageOrientationPatient'] = rawMetadata['ImageOrientationPatient'].value[0]

    if 'ImagePositionPatient' in metadataKeys:
        metadata['ImagePositionPatient'] = rawMetadata['ImagePositionPatient'].value[0]

    if 'FrameOfReferenceUID' in metadataKeys:
        metadata['FrameOfReferenceUID'] = _get_hdf5_string(rawMetadata['FrameOfReferenceUID'])

    return metadata


def _get_hdf5_string(hdf5_element):
    char_array = hdf5_element.value
    if np.max(char_array) < 20:
        return ''
    else:
        return char_array.tostring().decode('utf-16')


def _get_body_part(rawScan):
    if 'type' in rawScan['extraData']:
        scan_types = _parse_cell_of_strings(rawScan['extraData'], 'type', rawScan)
        if 'hemo' in scan_types:
            return 'brain'
        elif 'cspine' in scan_types:
            return 'cspine'
        else:
            logger.warning('Unsupported scan type: %s - assuming hemo', str(scan_types))
            return 'brain'
    else:
        logger.warning('Missing scan type - assuming hemo')
        return 'brain'


def _get_plane(rawScan):
    if 'plane' in rawScan['extraData']:
        plane = _get_hdf5_string(rawScan['extraData']['plane'])
        if 'ax' in plane:
            return 'axial'
        elif 'sag' in plane:
            return 'sagittal'
        elif 'cor' in plane:
            return 'coronal'
        else:
            raise Exception('Unsupported plane: ' + plane)
    else:
        raise Exception('Missing scan plane')


def _is_simulated_short_scan(rawScan):
    extraData = rawScan['extraData']

    if 'specialmarks' not in extraData:
        return True
    else:
        for ind, text_cell in enumerate(extraData['specialmarks']):
            if isinstance(text_cell.item(), int):  # Happens when specialmarks is an empty cell array
                return True

            decoded = rawScan[text_cell.item()].value.tostring().decode('utf-16')
            if 'short' in decoded:
                return False

        return True


def _parse_cell_of_strings(dataset, key, rawScan):
    values = []
    for text_cell in dataset[key]:
        if isinstance(text_cell.item(), int):  # Happens when the key contains an empty cell array
            return []

        decoded = _get_hdf5_string(rawScan[text_cell.item()])
        values.append(decoded)

    return values


def _is_empty_metadata(metadata_obj):
    if isinstance(metadata_obj, h5py._hl.group.Group) and len(metadata_obj) > 0:
        return False
    if isinstance(metadata_obj, h5py._hl.dataset.Dataset):
        l = metadata_obj.size
        for i in range(l):
            if not metadata_obj[i] == 0:
                return False
    else:
        raise Exception('Unknown type of all_metadata field')
    return True


def _read_image_positions(rawScan, num_slices, plane):
    image_positions = []

    if 'all_metadata' in rawScan and not (_is_empty_metadata(rawScan['all_metadata'])):
        all_metadata = rawScan['all_metadata']
        image_positions_refs = all_metadata['ImagePositionPatient']
        for ref in image_positions_refs:
            image_position = rawScan[ref[0]].value[0]
            image_positions.append(image_position.tolist())
    else:
        first_slice_metadata = _read_metadata(rawScan, rawScan['metadata'])
        if 'SpacingBetweenSlices' not in first_slice_metadata:
            raise Exception('Cannot obtain image position patient info for all slices')

        # Try to guess the image positions for all slices by using SpacingBetweenSlices
        # Note that this isn't accurate and might not even be correct since SpacingBetweenSlices is unreliable
        # TODO: Try to use the first and last slices' metadata to get a more accurate image position
        slice_spacing = first_slice_metadata['SpacingBetweenSlices']
        first_slice_position = np.array(first_slice_metadata['ImagePositionPatient'])

        if plane == 'axial':
            z_idx = 2
        elif plane == 'sagittal':
            z_idx = 0
        elif plane == 'coronal':
            z_idx = 1
        else:
            raise Exception('Unknown orientation: ' + plane)

        for i in np.arange(num_slices):
            slice_position = np.array(first_slice_position)
            slice_position[z_idx] += i * slice_spacing
            image_positions.append(slice_position)

    # if 'lastSliceInfo' not in rawScan['metadata']:
    #     raise Exception('Cannot obtain image position patient info for all slices')
    #
    # logger.warning('CTscan is missing the "all_metadata" field - trying to reconstruct image position patient for '
    #                'all slices')
    #
    # first_slice_metadata = _read_metadata(rawScan, rawScan['metadata'])
    # last_slice_metadata = _read_metadata(rawScan, rawScan['metadata']['lastSliceInfo'])
    # first_slice_position = first_slice_metadata['ImagePositionPatient']
    # last_slice_position = last_slice_metadata['ImagePositionPatient']
    # interpolated_positions = []
    # for i in range(3):
    #     interpolated_positions.append(np.linspace(first_slice_position[i], last_slice_position[i], num=num_slices))
    # image_positions = np.transpose(interpolated_positions, (1, 0))

    return image_positions


uids = ['993855875AX_ CT',
        '993849679AX_ CT',
        '993834903AX_ CT',
        '993826633AX_ CT',
        '993822061AX_ CT',
        '993821053AX_ CT',
        '993810264AX_ CT',
        '993810236AX_ CT',
        '993785482AX_ CT',
        '993782728AX_ CT',
        '993779655AX_ CT',
        '993768397AX_ CT',
        '993767576AX_ CT',
        '993763226AX_ CT',
        '993760760AX_ CT',
        '993757947AX_ CT',
        '993749951AX_ CT',
        '993744984AX_ CT',
        '993729638AX_ CT',
        '993729047AX_ CT',
        '993724361AX_ CT',
        '993704772AX_ CT',
        '993693511AX_ CT',
        '993686932AX_ CT',
        '993684416AX_ CT',
        '993678950AX_ CT',
        '993671430AX_ CT',
        '993637426AX_ CT',
        '993591641AX_ CT',
        '993556533AX_ CT',
        '993527536AX_ CT',
        '993486021AX_ CT',
        '993429173AX_ CT',
        '993428743AX_ CT',
        '993401414AX_ CT',
        '993390417AX_ CT',
        '993366272AX_ CT',
        '993878779AX_ CT',
        '993825818AX_ CT',
        '993720996AX_ CT',
        '993879969AX_ CT',
        '993715260AX_ CT',
        '993829897AX_ CT',
        '993601888AX_ CT',
        '993834953AX_ CT',
        '993701771AX_ CT',
        '1.3.46.670589.33.1.63576115094373719500002.4954112684291476023',
        '1.2.840.113704.1.111.11008.1351936189.7',
        '1.2.840.113704.1.111.13808.1503898484.11',
        '1.2.840.113619.2.327.3.363645206.101.1491974371.77.3',
        '1.2.840.113704.1.111.7608.1361981364.7',
        '1.2.840.113704.1.111.5616.1456669714.11',
        '1.2.840.113704.1.111.6804.1415148332.11',
        '1.2.840.113704.1.111.6832.1450449889.11',
        '1.2.840.113704.1.111.11656.1418117507.7',
        '1.2.840.113704.1.111.11796.1399021368.10',
        '1.2.840.113704.1.111.6780.1450465766.10',
        '1.2.840.113704.1.111.7452.1417088632.9',
        '1.2.840.113704.1.111.6852.1419238283.12',
        '1.2.840.113704.1.111.8744.1350938660.7',
        '1.2.840.113704.1.111.10668.1377019262.7',
        '1.2.840.113704.1.111.5376.1457801932.15',
        '1.2.840.113704.1.111.6672.1459643814.11',
        '1.2.840.113704.1.111.6772.1373629102.7',
        '1.2.840.113704.1.111.12240.1458491978.11',
        '1.2.840.113704.1.111.1260.1458059886.11',
        '1.2.840.113704.1.111.4936.1415276112.8',
        '1.2.840.113704.1.111.11136.1453757395.11',
        '1.2.840.113704.1.111.8160.1452076113.16',
        '1.2.840.113704.1.111.7212.1422371159.8'
        ]

if __name__ == '__main__':

    for uid in uids[0:1]:
        try:
            scan = Scan.fromID(uid, read_volume=True)
            print(uid)
            print(scan.metadata)
            print(scan.size)
            print(np.min(scan.volume[1]))
            print(np.max(scan.volume[1]))

        except OSError:
            continue
