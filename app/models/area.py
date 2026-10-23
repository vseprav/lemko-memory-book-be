from app.extensions import db


class Oblast(db.Model):
    """A destination of the eviction: an oblast of the УРСР, or a unit of another republic."""
    __tablename__ = 'oblasts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)  # as the book names it: Сталінська
    modern_name = db.Column(db.Text)  # Донецька; null when the unit no longer exists
    republic = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'modern_name': self.modern_name,
            'republic': self.republic,
        }


class Area(db.Model):
    """One value of "область виселення" as printed in the book, linked to the oblast it names
    where the reading is plain (line-break hyphens, "нині …" notes, towns, typos) and unlinked
    where the book is ambiguous ("Тернопільська Львівська?")."""
    __tablename__ = 'areas'
    id = db.Column(db.Integer, primary_key=True)
    printed = db.Column(db.Text, nullable=False, unique=True)
    oblast_id = db.Column(db.Integer, db.ForeignKey('oblasts.id'))
    locality = db.Column(db.Text)  # the town named in the value, e.g. "м. Одеса" -> Одеса
    uncertain = db.Column(db.Boolean, nullable=False, default=False)  # printed with a "?"

    oblast = db.relationship('Oblast')
