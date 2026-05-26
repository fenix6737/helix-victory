import { MachineDetailView } from "./MachineDetailView";

type Props = { params: Promise<{ id: string }> };

export default async function MachinePage({ params }: Props) {
  const { id } = await params;
  const machineId = parseInt(id, 10);
  if (Number.isNaN(machineId)) {
    return <main className="p-8 text-center">台が見つかりません</main>;
  }
  return <MachineDetailView machineId={machineId} />;
}
