import { iconStyleFromTitle, machineInitials } from "@/lib/machineVisual";

type Props = {
  title: string;
  gameType: "slot" | "pachinko";
  size?: "sm" | "md" | "lg";
};

const SIZE = { sm: 40, md: 52, lg: 64 };
const FONT = { sm: "text-xs", md: "text-sm", lg: "text-base" };

/** 機種名ベースの台アイコン（タイトルごとに色・略称が変わる） */
export function MachineIcon({ title, gameType, size = "md" }: Props) {
  const px = SIZE[size];
  const style = iconStyleFromTitle(title, gameType);
  const initials = machineInitials(title, gameType);
  const showTypeBadge =
    gameType === "slot" ||
    (gameType === "pachinko" && initials !== "P" && !/^[ぱパ]/.test(initials));

  return (
    <div
      className="relative flex shrink-0 items-center justify-center rounded-2xl ring-1 ring-white/10"
      style={{ width: px, height: px, ...style }}
      title={title}
      aria-label={title}
    >
      <span
        className={`${FONT[size]} font-extrabold leading-none text-white drop-shadow-md`}
      >
        {initials}
      </span>
      {showTypeBadge && (
        <span
          className={`absolute -bottom-1 -right-1 rounded-md px-1 py-0.5 text-[9px] font-bold ${
            gameType === "pachinko"
              ? "bg-pink-600 text-white"
              : "bg-amber-600 text-white"
          }`}
        >
          {gameType === "pachinko" ? "P" : "S"}
        </span>
      )}
    </div>
  );
}
