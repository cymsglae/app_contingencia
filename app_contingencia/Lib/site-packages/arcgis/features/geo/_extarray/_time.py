from __future__ import annotations
import pandas as pd
import datetime
import pyarrow as pa
import numpy as np

try:
    from pandas import ArrowDtype
except ImportError:
    from pandas.core.arrays.arrow.dtype import ArrowDtype


class ArrowTimeDtype(pd.api.extensions.ExtensionDtype):
    name = "arrow[time]"
    type = datetime.time
    # kind = datetime.time

    @classmethod
    def construct_array_type(cls):
        return ArrowTimeArray


class ArrowTimeArray(pd.core.arrays.ArrowExtensionArray):
    def __init__(self, values: pa.Array | pa.ChunkedArray):
        if isinstance(values, pa.Array):
            self._data = pa.chunked_array([values])
        elif isinstance(values, pa.ChunkedArray):
            self._data = values
        elif isinstance(values, np.ndarray):
            self._data = pa.chunked_array([values])

        else:
            raise ValueError(
                f"Unsupported type '{type(values)}' for ArrowExtensionArray"
            )
        self._dtype = ArrowDtype(self._data.type)
        self.data = self._data
        self._pa_array = self._data

    @property
    def dtype(self) -> ArrowTimeDtype:
        return ArrowTimeDtype()

    def __len__(self):
        return len(self._data)

    def isna(self):
        return pd.isna(self._data)

    # -------------------------------------------------------------------------
    # ExtensionArray specific
    # -------------------------------------------------------------------------

    def __array__(self, dtype=None):
        """
        The numpy array interface.

        Returns
        -------
        values : numpy array
        """
        return self._data.to_numpy()

    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy=False):
        """
        Construct a new ExtensionArray from a sequence of scalars.

        Parameters
        ----------
        scalars : Sequence
            Each element will be an instance of the scalar type for this
            array, ``cls.dtype.type``.
        dtype : dtype, optional
            Construct for this particular dtype. This should be a Dtype
            compatible with the ExtensionArray.
        copy : boolean, default False
            If True, copy the underlying data.

        Returns
        -------
        ExtensionArray
        """
        data = np.empty(len(scalars), dtype=object)
        data[:] = scalars
        return cls(data)


@pd.api.extensions.register_series_accessor("time")
class ArrowTimeAccessor:
    def __init__(self, series: pd.Series):
        self._validate(series)
        self._series = series

    @staticmethod
    def _validate(series):
        if not isinstance(series.dtype, ArrowTimeDtype):
            raise AttributeError("Series must have dtype 'arrow_time'.")

    @property
    def hour(self) -> pd.Series:
        """returns the series hour value"""
        return self._series.apply(
            lambda x: x.hour if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    @property
    def minute(self) -> pd.Series:
        """returns the series minute value"""
        return self._series.apply(
            lambda x: x.minute if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    @property
    def second(self) -> pd.Series:
        """returns the series second value"""
        return self._series.apply(
            lambda x: x.second if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    @property
    def microsecond(self) -> pd.Series:
        """returns the series microsecond value"""
        return self._series.apply(
            lambda x: x.microsecond if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    @property
    def tzinfo(self) -> pd.Series:
        """returns the time zone information"""
        return self._series.apply(
            lambda x: x.tzinfo if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    def isoformat(self, timespec: str = "auto") -> pd.Series:
        """
        Return a string representing the time in ISO 8601 format
        """
        return self._series.apply(
            lambda x: x.isoformat(timespec=timespec) if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    def strformat(self, format_str: str) -> pd.Series:
        """
        Return a string representing the time, controlled by an explicit format string.
        """
        return self._series.apply(
            lambda x: x.strftime(format_str) if not pd.isna(x) else None,
            convert_dtype=True,
        ).convert_dtypes()

    def replace(
        self,
        hour: int | None = None,
        minute: int | None = None,
        second: int | None = None,
        microsecond: int | None = None,
        tzinfo: datetime.tzinfo | None = None,
        *,
        fold: int = 0,
    ) -> pd.Series:
        """
        Return a string representing the time, controlled by an explicit format string.
        """

        def _replace(
            x: datetime.time,
            hour: int | None = None,
            minute: int | None = None,
            second: int | None = None,
            microsecond: int | None = None,
            tzinfo: datetime.tzinfo | None = None,
            *,
            fold: int = 0,
        ):
            if hour is None:
                hour = x.hour
            if minute is None:
                minute = x.minute
            if second is None:
                second = x.second
            if microsecond is None:
                microsecond = x.microsecond
            if tzinfo is None:
                tzinfo = x.tzinfo
            return x.replace(
                hour=hour,
                minute=minute,
                second=second,
                microsecond=microsecond,
                tzinfo=tzinfo,
                fold=fold,
            )

        if (
            hour is None
            and minute is None
            and second is None
            and microsecond is None
            and tzinfo is None
            and fold == 0
        ):
            return self._series.convert_dtypes()

        return (
            self._series.apply(
                lambda x: (
                    _replace(
                        x,
                        hour=hour,
                        minute=minute,
                        second=second,
                        microsecond=microsecond,
                        fold=fold,
                        tzinfo=tzinfo,
                    )
                    if not pd.isna(x)
                    else None
                ),
                convert_dtype=True,
            )
            .convert_dtypes()
            .astype(ArrowTimeDtype())
        )


pd.api.extensions.register_extension_dtype(ArrowTimeDtype)
