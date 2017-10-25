from flask import Flask, render_template, request, make_response, jsonify
from scan import Scan, uids
import uuid
import json
import os


def load_rois():
    rois_by_scan = {}
    dir = 'simple_imagine/rois'
    for file in os.listdir(dir):
        file_path = os.path.join(dir, file)

        rois = []
        with open(file_path) as infile:
            for line in infile:
                rois.append(json.loads(line))
        rois_by_scan[file] = rois

    return rois_by_scan


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config['DEBUG'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'

    # db.init_app(app)

    rois_by_scan = load_rois()

    @app.route('/')
    def worklist():
        scans = []

        for uid in uids:
            try:
                scan = Scan.fromID(uid, read_volume=False)

                scans.append(
                    {'accessionNumber': scan.metadata['AccessionNumber'], 'patientName': scan.name, 'uid': scan.uid})

            except OSError:
                continue

        return render_template('index.html', scans=scans)

    @app.route('/view-scan/<uid>')
    def view_scan(uid):
        scan = Scan.fromID(uid, read_volume=False)
        print(uid)
        print(scan.metadata)
        print(scan.size)
        return render_template('view_scan.html', scan=scan)

    @app.route('/get-scan/<uid>')
    def get_scan(uid):
        scan = Scan.fromID(uid, read_volume=True)
        print(uid)
        print(scan.metadata)

        volume = scan.volume.tobytes()

        response = make_response(volume)
        response.headers['Content-Length'] = len(volume)
        response.headers['Content-Type'] = 'application/octet-stream'
        return response

    @app.route('/add-roi', methods=["POST"])
    def add_roi():
        content = request.get_json(force=True)

        scan_id = content['scan_id']

        x = content['x']
        y = content['y']
        w = content['w']
        h = content['h']
        color = content['color']

        slice = content['image_index']
        roi = {'id': str(uuid.uuid1()), 'label': 'ROI ' + str(slice), 'slice': slice, 'color': color, 'x': x, 'y': y,
               'w': w,
               'h': h}

        rois = get_rois_by_uid(scan_id)

        rois.append(roi)
        return jsonify(roi)

    @app.route('/delete-roi', methods=["POST"])
    def delete_roi():
        content = request.get_json(force=True)

        scan_id = content['scan_id']
        group_id = content['id']

        rois = get_rois_by_uid(scan_id)

        for roi in rois[:]:
            if roi['color'] == group_id:
                rois.remove(roi)

        print("Deleted " + group_id + "," + str(rois))
        return jsonify(rois)

    @app.route('/get-rois/<uid>/<slice>')
    def get_rois(uid, slice):

        rois = get_rois_by_uid(uid)

        rois_in_slice = []
        for roi in rois:
            if roi['slice'] == int(slice):
                rois_in_slice.append(roi)
        return jsonify(rois_in_slice)

    @app.route('/get-roi-groups/<uid>')
    def get_roi_groups(uid):
        rois = get_rois_by_uid(uid)

        roi_groups = {}

        for roi in rois:
            color = roi['color']

            if color not in roi_groups:
                roi_groups[color] = {'label': 'ROI', 'min_slice': roi['slice'], 'max_slice': roi['slice'],
                                     'color': color}
            else:
                roi_groups[color]['min_slice'] = min(roi['slice'], roi_groups[color]['min_slice'])
                roi_groups[color]['max_slice'] = max(roi['slice'], roi_groups[color]['max_slice'])

        return jsonify(list(roi_groups.values()))

    @app.route('/save', methods=['POST'])
    def save():
        content = request.get_json(force=True)

        scan_id = content['scan_id']
        rois = get_rois_by_uid(scan_id)

        with open('simple_imagine/rois/' + scan_id, 'a') as outfile:
            for roi in rois:
                json.dump(roi, outfile)
                outfile.write('\n')

        return ""

    def get_rois_by_uid(uid):

        if uid not in rois_by_scan:
            rois_by_scan[uid] = []

        return rois_by_scan[uid]

    return app


if __name__ == '__main__':
    create_app().run()
