"""Tests del motor de disponibilidad (E2).

La función hay_solapamiento es lógica pura (no toca la base), así que la
testeamos directamente con muchos casos. Es el núcleo que impide la doble
reserva: si esto se rompe, todo el sistema de turnos queda comprometido.
"""

import datetime as dt

from app.services.disponibilidad import hay_solapamiento


def _t(hora: int, minuto: int = 0) -> dt.datetime:
    """Helper: crea un datetime en una fecha fija, a la hora dada."""
    return dt.datetime(2026, 6, 15, hora, minuto, tzinfo=dt.timezone.utc)


class TestSolapamiento:
    """Casos de la regla de oro: ini_a < fin_b AND ini_b < fin_a."""

    def test_turnos_contiguos_no_chocan(self):
        """15:00-15:30 y 15:30-16:00 comparten solo el instante límite → NO chocan."""
        a = (_t(15, 0), _t(15, 30))
        b = (_t(15, 30), _t(16, 0))
        assert hay_solapamiento(*a, *b) is False

    def test_turnos_superpuestos_chocan(self):
        """15:00-15:30 y 15:15-15:45 se pisan en el medio → SÍ chocan."""
        a = (_t(15, 0), _t(15, 30))
        b = (_t(15, 15), _t(15, 45))
        assert hay_solapamiento(*a, *b) is True

    def test_turno_contenido_choca(self):
        """Un turno completamente dentro de otro → chocan."""
        grande = (_t(15, 0), _t(16, 0))
        chico = (_t(15, 15), _t(15, 30))
        assert hay_solapamiento(*grande, *chico) is True

    def test_turnos_identicos_chocan(self):
        """Dos turnos en exactamente el mismo horario → chocan."""
        a = (_t(15, 0), _t(15, 30))
        assert hay_solapamiento(*a, *a) is True

    def test_turnos_separados_no_chocan(self):
        """15:00-15:30 y 16:00-16:30, con un hueco entre medio → no chocan."""
        a = (_t(15, 0), _t(15, 30))
        b = (_t(16, 0), _t(16, 30))
        assert hay_solapamiento(*a, *b) is False

    def test_solapamiento_es_simetrico(self):
        """El orden de los argumentos no cambia el resultado."""
        a = (_t(15, 0), _t(15, 30))
        b = (_t(15, 15), _t(15, 45))
        assert hay_solapamiento(*a, *b) == hay_solapamiento(*b, *a)

    def test_solapamiento_minimo_de_un_minuto(self):
        """Aunque se pisen solo 1 minuto, chocan."""
        a = (_t(15, 0), _t(15, 31))
        b = (_t(15, 30), _t(16, 0))
        assert hay_solapamiento(*a, *b) is True