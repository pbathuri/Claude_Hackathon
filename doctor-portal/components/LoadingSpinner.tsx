export default function LoadingSpinner({ text = "Loading..." }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <div className="w-8 h-8 border-[2.5px] border-gray-200 border-t-who-blue rounded-full animate-spin mb-4" />
      <p className="text-sm font-medium">{text}</p>
    </div>
  );
}
