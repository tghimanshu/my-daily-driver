export interface WeatherData {
  temp: number;
  code: number;
  desc: string;
  humidity?: number;
  windSpeed?: number;
  feelsLike?: number;
  location?: string;
}

export async function fetchWeather(
  lat = 37.7749,
  lon = -122.4194
): Promise<WeatherData | null> {
  try {
    const res = await fetch(
      `https://api.open-meteo.com/v1/forecast?` +
        `latitude=${lat}&longitude=${lon}&` +
        `current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m&` +
        `temperature_unit=fahrenheit&wind_speed_unit=mph`,
      { next: { revalidate: 1800 } } // Cache 30 mins
    );

    if (!res.ok) throw new Error("Weather fetch failed");
    const data = await res.json();

    return {
      temp: Math.round(data.current.temperature_2m),
      code: data.current.weather_code,
      desc: getWeatherDesc(data.current.weather_code),
      humidity: data.current.relative_humidity_2m,
      windSpeed: Math.round(data.current.wind_speed_10m),
      feelsLike: Math.round(data.current.apparent_temperature),
    };
  } catch (e) {
    console.error("Weather API Error:", e);
    return null;
  }
}

export async function fetchWeatherByCity(
  city: string
): Promise<WeatherData | null> {
  try {
    // First, get coordinates from city name using geocoding API
    const geoRes = await fetch(
      `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(
        city
      )}&count=1&language=en&format=json`
    );

    if (!geoRes.ok) return null;
    const geoData = await geoRes.json();

    if (!geoData.results || geoData.results.length === 0) return null;

    const { latitude, longitude, name } = geoData.results[0];
    const weather = await fetchWeather(latitude, longitude);

    if (weather) {
      weather.location = name;
    }

    return weather;
  } catch (e) {
    console.error("Weather by city error:", e);
    return null;
  }
}

function getWeatherDesc(code: number): string {
  if (code === 0) return "Clear Sky";
  if (code <= 2) return "Partly Cloudy";
  if (code === 3) return "Overcast";
  if (code <= 49) return "Foggy";
  if (code <= 69) return "Rainy";
  if (code <= 79) return "Snowy";
  if (code <= 84) return "Showers";
  return "Stormy";
}

export function getWeatherEmoji(code: number): string {
  if (code === 0) return "☀️";
  if (code <= 2) return "⛅";
  if (code === 3) return "☁️";
  if (code <= 49) return "🌫️";
  if (code <= 69) return "🌧️";
  if (code <= 79) return "🌨️";
  if (code <= 84) return "🌦️";
  return "⛈️";
}
