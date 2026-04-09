from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, Optional


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


CHART_CHOICES = [
    ("bar",       "📊 Bar Chart"),
    ("line",      "📈 Line Chart"),
    ("scatter",   "🔵 Scatter Plot"),
    ("pie",       "🥧 Pie Chart"),
    ("box",       "📦 Box Plot"),
    ("histogram", "📉 Histogram"),
    ("area",      "🏔️ Area Chart"),
    ("heatmap",   "🌡️ Heatmap (Correlation)"),
    ("violin",    "🎻 Violin Plot"),
]


class UploadForm(FlaskForm):
    csv_file = FileField(
        "Upload CSV File",
        validators=[
            DataRequired(message="Please select a CSV file."),
            FileAllowed(["csv"], "Only .csv files are allowed."),
        ],
    )
    chart_type = SelectField("Chart Type", choices=CHART_CHOICES)
    x_col = StringField("X-Axis Column (optional)", validators=[Optional()])
    y_col = StringField("Y-Axis Column (optional)", validators=[Optional()])
    submit = SubmitField("Upload & Analyze")
