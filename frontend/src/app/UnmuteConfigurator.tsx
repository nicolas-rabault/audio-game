import { useCallback, useEffect, useState } from "react";
import VoiceAttribution from "./VoiceAttribution";
import SquareButton from "./SquareButton";
import Modal from "./Modal";
import { ArrowUpRight } from "lucide-react";
import VoiceUpload from "./VoiceUpload";
// import VoiceUpload from "./VoiceUpload";

export type LanguageCode = "en" | "fr" | "en/fr" | "fr/en";

export type UnmuteConfig = {
  voice: string;
  // The backend doesn't care about this, we use it for analytics
  voiceName: string;
};

// Will be overridden immediately by the voices fetched from the backend
export const DEFAULT_UNMUTE_CONFIG: UnmuteConfig = {
  voice: "barack_demo.wav",
  voiceName: "Missing voice",
};

export type FreesoundVoiceSource = {
  source_type: "freesound";
  url: string;
  start_time: number;
  sound_instance: {
    id: number;
    name: string;
    username: string;
    license: string;
  };
  path_on_server: string;
};

export type FileVoiceSource = {
  source_type: "file";
  path_on_server: string;
  description?: string;
  description_link?: string;
};

export type VoiceSample = {
  name: string | null;
  comment: string;
  good: boolean;
  source: FreesoundVoiceSource | FileVoiceSource;
};

const fetchVoices = async (
  backendServerUrl: string
): Promise<VoiceSample[]> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(`${backendServerUrl}/v1/voices`, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      console.error("Failed to fetch voices:", response.statusText);
      return [];
    }

    const voices = await response.json();
    return voices;
  } catch (error) {
    console.error("Error fetching voices:", error);
    return [];
  }
};

const getVoiceName = (voice: VoiceSample) => {
  return (
    voice.name ||
    (voice.source.source_type === "freesound"
      ? voice.source.sound_instance.username
      : voice.source.path_on_server.slice(0, 10))
  );
};

const UnmuteConfigurator = ({
  config,
  backendServerUrl,
  setConfig,
  voiceCloningUp,
}: {
  config: UnmuteConfig;
  backendServerUrl: string;
  setConfig: (config: UnmuteConfig) => void;
  voiceCloningUp: boolean;
}) => {
  const [voices, setVoices] = useState<VoiceSample[] | null>(null);
  const [customVoiceName, setCustomVoiceName] = useState<string | null>(null);

  useEffect(() => {
    const fetchVoicesData = async () => {
      if (backendServerUrl && voices === null) {
        const voicesData = await fetchVoices(backendServerUrl);
        setVoices(voicesData);

        const randomVoice =
          voicesData[Math.floor(Math.random() * voicesData.length)];

        setConfig({
          ...config,
          voice: randomVoice.source.path_on_server,
          voiceName: getVoiceName(randomVoice),
        });
      }
    };

    fetchVoicesData();
  }, [backendServerUrl, config, setConfig, voices]);

  const onCustomVoiceUpload = useCallback(
    (name: string) => {
      setCustomVoiceName(name);
      setConfig({
        voice: name,
        voiceName: "custom",
      });
    },
    [setConfig]
  );

  if (!voices) {
    return (
      <div className="w-full">
        <p className="text-lightgray">Loading voices...</p>
      </div>
    );
  }

  const activeVoice = voices.find(
    (voice) => voice.source.path_on_server === config.voice
  );

  return (
    <div className="w-full flex flex-col items-center">
      {/* Separate header div, because it has a different background */}
      <div className="w-full max-w-6xl grid grid-flow-row grid-cols-1 gap-3 px-3">
        <div className="w-full flex flex-row items-center gap-2">
          <Modal
            trigger={
              <h2 className="pb-1 cursor-pointer flex items-center gap-1 text-lightgray">
                Character <ArrowUpRight size={24} />
              </h2>
            }
          >
            <p>
              The voice of the text-to-speech is based on a 10-second sample.
            </p>
            {activeVoice && <VoiceAttribution voice={activeVoice} />}
          </Modal>
          <div className="h-0.5 bg-gray grow hidden md:visible"></div>
        </div>
      </div>
      {/* Gray background div, full width */}
      <div className="w-full md:bg-gray flex flex-col items-center">
        <div className="w-full max-w-6xl grid grid-flow-row grid-cols-2 md:grid-cols-3 gap-3 p-3">
          {voices &&
            voices.map((voice) => (
              <SquareButton
                key={voice.source.path_on_server}
                onClick={() => {
                  setConfig({
                    voice: voice.source.path_on_server,
                    voiceName: voice.name || "Unnamed",
                  });
                }}
                kind={
                  voice.source.path_on_server === config.voice
                    ? "primary"
                    : "secondary"
                }
                extraClasses="bg-gray md:bg-black"
              >
                {"/ " + getVoiceName(voice) + " /"}
              </SquareButton>
            ))}
          {voiceCloningUp && (
            <VoiceUpload
              backendServerUrl={backendServerUrl}
              onCustomVoiceUpload={onCustomVoiceUpload}
              isSelected={customVoiceName === config.voice}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default UnmuteConfigurator;
