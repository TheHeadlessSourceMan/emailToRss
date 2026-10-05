"""
Wrapper around a YAML/JSON configuration file.
Provides dictionary-like access to settings.
"""
import typing
from pathlib import Path
DEFAULT_SETTINGS_FILENAME=Path(__file__).parent/'data'/'settings.yaml'


class Settings:
    """
    Wrapper around a YAML/JSON configuration file.
    Provides dictionary-like access to settings.
    """
    def __init__(self,
        filename:typing.Union[None,str,Path]=DEFAULT_SETTINGS_FILENAME):
        """ """
        if filename is None:
            filename=DEFAULT_SETTINGS_FILENAME
        if isinstance(filename,str):
            filename=Path(filename)
        self._filename=filename
        self._settings:typing.Optional[typing.Dict[str,typing.Any]]=None

    def load(self,filename:typing.Union[None,str,Path]=None):
        """
        Load the settings from the specified YAML file.
        """
        if filename is None:
            filename=self._filename
        elif not isinstance(filename,Path):
            filename=Path(filename)
        if filename.suffix in ('.yaml','.yml'):
            import yaml
            data=filename.read_text(encoding='utf-8',errors='ignore')
            self._settings=yaml.safe_load(data)
        elif filename.suffix=='.json':
            import json
            data=filename.read_text(encoding='utf-8',errors='ignore')
            self._settings=json.loads(data)
        else:
            raise ValueError(f"Unsupported file type: {filename.suffix}")

    def __getitem__(self,key:str)->typing.Any:
        if self._settings is None:
            self.load()
        return self._settings[key] # type: ignore

    def get(self,key:str,default:typing.Any=None)->typing.Any:
        """
        Access like a dict
        """
        if self._settings is None:
            self.load()
        return self._settings.get(key,default) # type: ignore
