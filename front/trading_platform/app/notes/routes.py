from flask import jsonify, request
from app.notes import bp
from app.notes.models import Note
from app import db

@bp.route('/save', methods=['POST'])
def save_note():
    try:
        content = request.json.get('note')
        if content:
            note = Note(content=content)
            db.session.add(note)
            db.session.commit()
            return jsonify({'success': True, 'note': note.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/list')
def list_notes():
    try:
        notes = Note.query.order_by(Note.timestamp.desc()).all()
        return jsonify([note.to_dict() for note in notes])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}) 