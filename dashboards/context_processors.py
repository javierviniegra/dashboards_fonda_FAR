from . import motor_central


def version_motor(request):
    """Engine commit, shown in the footer of every page (traceability)."""
    return {"version_motor": motor_central.version()}
