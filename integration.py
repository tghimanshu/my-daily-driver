from abc import ABC, abstractmethod


class Integration(ABC):
    registry = {}

    def __init__(self, name):
        self._name = name
        self._settings = {}
        self._is_authenticated = False

    # Note: This will help us to automatically register our subclasses to the factory registry without having to manually add them. So cool!
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Integration.registry[cls.__name__] = cls

    @property
    def name(self):
        return self._name

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, value):
        if self._validate_settings(value):
            self._settings = value
        else:
            raise ValueError("Invalid settings provided.")

    @abstractmethod
    def get_user_info(self, user):
        pass

    @abstractmethod
    def authenticate(self, credentials):
        pass

    @property
    def is_authenticated(self):
        return self._is_authenticated

    @abstractmethod
    def get_access_token(self):
        pass

    @abstractmethod
    def logout(self):
        pass

    def _validate_settings(self, settings):
        """
        Validate the provided settings for the integration.
        Override if needed in subclasses to implement specific validation logic.
        """
        return True

    @abstractmethod
    def core_functionality(self):
        """
        This method should be implemented by subclasses to provide the core functionality of the integration.
        it can be fetching aggregated data, sending data to a service, or any other specific task that the integration is designed to perform as the main purpose of the integration.
        This method should be called by the main application to execute the integration's primary function (or like get the main widget of the integration).
        The implementation of this method will vary depending on the specific integration and its intended use case.
        """
